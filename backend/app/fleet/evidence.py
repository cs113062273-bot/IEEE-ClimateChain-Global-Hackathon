"""Car-park control record: one replayed day, canonical and independently checkable.

The record separates what the controller knew (decision_inputs) from what
happened (outcomes) and what it did (record). scripts/verify_carpark.py checks it
without importing this package.
"""
from __future__ import annotations
import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from backend.app.services import storage
from backend.app.services.evidence import normalize, canonical_bytes, digest
from .controller import Site
from .grid import grid_day
from .sessions import ROOT, SOURCE, raw_sha256

sys.path.insert(0, str(ROOT / "scripts"))
import verify_carpark  # noqa: E402  (stdlib-only independent verifier)

SITE_ID = "gridproof-workplace-carpark-railsEM-gb-replay-v1"
SITE_HASH = "0x" + hashlib.sha256(SITE_ID.encode()).hexdigest()
CATEGORY = "workplace-charging-control-record"


def _commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def build(run_id):
    run = storage.get(run_id, "carpark")
    grid = grid_day(run["grid_date"])
    site = Site(connection_kw=run["connection_kw"])
    claim = {
        "schema": "gridproof-carpark-evidence-v1",
        "canonicalization": "gridproof-canonical-json-v1/float-decimal-strings-9",
        "claim_scope": {"site_hash": SITE_HASH, "from_utc": grid["start_utc"][0],
                        "to_utc": grid["start_utc"][-1][:11] + "23:59:59Z", "category": CATEGORY},
        "observational_status": "historical_replay_simulation",
        "sources": {
            "sessions": {**SOURCE, "sha256": raw_sha256(), "session_date": run["date"], "transform": run["input_transform"],
                         "anchor_manifest": "data/trust/carpark_anchors.v1.json"},
            "grid": {"grid_date": run["grid_date"], "anchor_manifest": "data/trust/source_anchors.v1.json",
                     "sha256": run["grid_sources_sha256"], "forecast_method": grid["forecast_method"]},
        },
        "controller": {"mode": run["mode"], "policy": run["policy"], "description": run["policy_description"],
                       "site_parameters": asdict(site), "departure_model": run["model"]},
        "decision_inputs": {
            "connection_kw": run["connection_kw"],
            "cars": [{k: c[k] for k in ("id", "driver", "arrival_h", "request_kwh", "max_kw", "promise_h", "risk")} for c in run["cars"]],
            "events": run["events"],
            "ci_forecast": grid["ci_forecast"].tolist(), "pv_forecast_kwh": grid["pv_forecast"].tolist(),
            "base_load_kwh": grid["base_load"].tolist(), "tariff": grid["tariff"].tolist(),
        },
        "outcomes": {"departures_h": {c["id"]: c["departure_h"] for c in run["cars"]},
                     "ci_actual": grid["ci_actual"].tolist(), "pv_outcome_kwh": grid["pv_outcome"].tolist()},
        "record": {"executed_kwh": {c["id"]: c["executed_kwh"] for c in run["cars"]},
                   "cap_kw": [s["cap_kw"] for s in run["slots"]]},
        "results": {**{k: run["metrics"][k] for k in ("sessions", "served", "delivered_kwh", "unserved_kwh", "emissions_kgco2", "cost_gbp", "peak_import_kw")},
                    "per_car": {c["id"]: {"delivered_kwh": c["delivered_kwh"], "unserved_kwh": c["unserved_kwh"]} for c in run["cars"]}},
        "reproduction": {"run_id": run_id, "code_commit": _commit(), "verifier": "scripts/verify_carpark.py"},
        "licence_notice": "Session-derived values come from a CC BY-NC-SA 4.0 dataset. Non-commercial use; consult the dataset contacts before redistributing.",
        "limitations": [
            "Historical replay: real workplace sessions (NL) on a same-weekday GB grid day; simulated chargers; synthetic base load and tariff",
            "Requests are the sessions' delivered energy, assumed declared at plug-in",
            "Location-based GB average carbon intensity; not causal avoided emissions or a credit",
            "Hashes and registry entries prove these bytes, not metering, execution or when the record was first written",
        ],
    }
    claim = normalize(claim)
    fingerprint = digest(claim)
    evidence_id = "carpark-evidence-" + fingerprint[:20]
    value = {"evidence_id": evidence_id, "digest": "0x" + fingerprint, "evidence": claim, "run_id": run_id}
    storage.put(evidence_id, "carpark-evidence", value)
    return value


def verify(evidence, expected_digest):
    return verify_carpark.inspect(evidence, expected_digest, ROOT)


def forge(evidence_id, attack):
    """Two deliberate forgeries, both rehashed so integrity alone passes."""
    proof = storage.get(evidence_id, "carpark-evidence")
    forged = copy.deepcopy(proof["evidence"])
    per_car = forged["results"]["per_car"]
    short = [cid for cid, v in per_car.items() if float(v["unserved_kwh"]) > 0.05]
    if attack == "hide_shortfall":
        # Claim every driver left full: top up recorded charging and results.
        target = short[0] if short else next(iter(per_car))
        row = [float(x) for x in forged["record"]["executed_kwh"][target]]
        gap = float(per_car[target]["unserved_kwh"]) or 1.0
        last = max((t for t, x in enumerate(row) if x > 0), default=20)
        row[last] += gap
        forged["record"]["executed_kwh"][target] = row
        per_car[target] = {"delivered_kwh": float(per_car[target]["delivered_kwh"]) + gap, "unserved_kwh": 0.0}
        forged["results"]["served"] = int(forged["results"]["served"]) + (1 if short else 0)
        forged["results"]["unserved_kwh"] = max(0.0, float(forged["results"]["unserved_kwh"]) - gap)
        forged["results"]["delivered_kwh"] = float(forged["results"]["delivered_kwh"]) + gap
        description = f"Added {gap:.2f} kWh to car {target}'s recorded charging and marked it fully served."
    elif attack == "move_departure":
        # Pretend a driver stayed 2 h longer and re-derive everything consistently.
        target = short[0] if short else next(iter(per_car))
        forged["outcomes"]["departures_h"][target] = float(forged["outcomes"]["departures_h"][target]) + 2.0
        executed, _, cars = verify_carpark.replay(forged["controller"]["policy"], forged["decision_inputs"], forged["outcomes"]) \
            if forged["controller"]["policy"] in verify_carpark.REPLAYABLE else (None, None, None)
        if executed is not None:
            forged["record"]["executed_kwh"] = executed
            for cid, row in executed.items():
                request = float(next(c["request_kwh"] for c in forged["decision_inputs"]["cars"] if c["id"] == cid))
                per_car[cid] = {"delivered_kwh": sum(row), "unserved_kwh": max(0.0, request - sum(row))}
            _recompute_results(forged)
        description = f"Moved car {target}'s departure 2 h later and recomputed charging and results consistently."
    elif attack == "drop_sessions":
        # Report a smaller day: leave out drivers who were short (or the last arrival) and recompute everything.
        cars = forged["decision_inputs"]["cars"]
        drop = set(short) or {max(cars, key=lambda c: float(c["arrival_h"]))["id"]}
        forged["decision_inputs"]["cars"] = [c for c in cars if c["id"] not in drop]
        forged["outcomes"]["departures_h"] = {k: v for k, v in forged["outcomes"]["departures_h"].items() if k not in drop}
        forged["record"]["executed_kwh"] = {k: v for k, v in forged["record"]["executed_kwh"].items() if k not in drop}
        forged["results"]["per_car"] = per_car = {k: v for k, v in per_car.items() if k not in drop}
        if forged["controller"]["policy"] in verify_carpark.REPLAYABLE:
            executed, _, _ = verify_carpark.replay(forged["controller"]["policy"], forged["decision_inputs"], forged["outcomes"])
            forged["record"]["executed_kwh"] = executed
            for c in forged["decision_inputs"]["cars"]:
                row = executed[c["id"]]
                per_car[c["id"]] = {"delivered_kwh": sum(row), "unserved_kwh": max(0.0, float(c["request_kwh"]) - sum(row))}
        forged["results"]["sessions"] = len(forged["decision_inputs"]["cars"])
        _recompute_results(forged)
        description = f"Left {len(drop)} driver(s) out of the day and recomputed charging and results consistently."
    else:
        raise ValueError("Unknown forgery")
    forged = normalize(forged)
    fresh = "0x" + digest(forged)
    return {"attack": attack, "description": description, "new_digest": fresh,
            "rehashed_verification": verify(forged, fresh), "original_digest_verification": verify(forged, proof["digest"]),
            "published": False}


def _recompute_results(forged):
    d, o, rec = forged["decision_inputs"], forged["outcomes"], forged["record"]
    base = [float(x) for x in d["base_load_kwh"]]; pv = [float(x) for x in o["pv_outcome_kwh"]]
    ev = [sum(float(rec["executed_kwh"][cid][t]) for cid in rec["executed_kwh"]) for t in range(48)]
    imports = [max(0.0, b + e - p) for b, e, p in zip(base, ev, pv)]
    per = forged["results"]["per_car"]
    forged["results"].update(
        served=sum(float(v["unserved_kwh"]) <= .05 for v in per.values()),
        unserved_kwh=sum(float(v["unserved_kwh"]) for v in per.values()),
        delivered_kwh=sum(float(v["delivered_kwh"]) for v in per.values()),
        emissions_kgco2=sum(m * float(c) for m, c in zip(imports, o["ci_actual"])) / 1000,
        cost_gbp=sum(m * float(c) for m, c in zip(imports, d["tariff"])), peak_import_kw=max(imports) / .5)


def canonical_text(value):
    return canonical_bytes(value).decode()
