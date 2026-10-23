"""Independent stdlib-only verifier for GridProof car-park control records.

  python scripts/verify_carpark.py evidence.json --digest 0x...

Imports no backend code. Layers, reported separately:
  integrity          canonical SHA256 equals the expected digest
  physical_service   cap with zero solar, presence, power limits, energy and metric arithmetic
  decision_replay    deterministic policies are re-run from decision-time inputs only
  source_lineage     grid values from pinned NESO/ERA5 bytes; sessions from the pinned raw file
A record can be internally consistent and still not correspond to its sources;
none of these layers proves physical metering, real execution or avoided emissions.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_evidence import sha, _load_pinned  # stdlib-only helpers shared with the v2 verifier

T = 48
DT = .5
TOL = 1e-6
CHECK_TOL = 2e-5
SERVED_TOL = .05
SCHEMA = "gridproof-carpark-evidence-v1"
REPLAYABLE = {"equal_share", "edf", "llf"}


def f(x):
    value = float(x)
    if not math.isfinite(value):
        raise ValueError("nonfinite number")
    return value


def first_slot(car):
    return int(math.ceil(car["arrival_h"] / DT - 1e-9))


def present(car, t):
    return 1.0 if first_slot(car) <= t and car["departure_h"] >= (t + 1) * DT - 1e-9 else 0.0


def deadline_slot(car, t):
    return min(T, max(t + 1, int(math.floor(car["promise_h"] / DT + 1e-9))))


def apply_events(events, cars, cap, t):
    for e in [e for e in events if int(e["at_slot"]) == t]:
        if e["type"] == "cap":
            for s in range(int(e["from_slot"]), int(e["to_slot"])):
                cap[s] = f(e["kw"])
        elif e["type"] == "leave":
            car = cars[e["car_id"]]
            car["departure_h"] = f(e["departure_h"]); car["promise_h"] = f(e["departure_h"])
        else:
            raise ValueError("unknown event type")


def allocate(policy, t, cars, remaining, base, cap):
    room = cap * DT - base
    if policy == "equal_share":
        limit = [min(c["max_kw"] * DT, r) for c, r in zip(cars, remaining)]
        out = [0.0] * len(cars); open_ = [l > TOL for l in limit]
        while room > TOL and any(open_):
            share = room / sum(open_)
            take = [min(share, limit[i] - out[i]) if open_[i] else 0.0 for i in range(len(cars))]
            out = [o + d for o, d in zip(out, take)]; room -= sum(take)
            open_ = [open_[i] and out[i] < limit[i] - TOL for i in range(len(cars))]
        return out
    if policy == "edf":
        order = sorted(range(len(cars)), key=lambda i: (deadline_slot(cars[i], t), -remaining[i], cars[i]["id"]))
    elif policy == "llf":
        laxity = [deadline_slot(c, t) - t - r / (c["max_kw"] * DT) for c, r in zip(cars, remaining)]
        order = sorted(range(len(cars)), key=lambda i: (laxity[i], cars[i]["id"]))
    else:
        raise ValueError("policy is not replayable")
    out = [0.0] * len(cars)
    for i in order:
        take = max(0.0, min(cars[i]["max_kw"] * DT, remaining[i], room)); out[i] = take; room -= take
    return out


def replay(policy, decision, outcomes):
    """Re-run the policy. Inputs: decision-time car fields, events, base load, cap,
    and each car's connection status at slot start. Nothing else."""
    cars = {c["id"]: {"id": c["id"], "arrival_h": f(c["arrival_h"]), "request_kwh": f(c["request_kwh"]),
                      "max_kw": f(c["max_kw"]), "promise_h": f(c["promise_h"]),
                      "departure_h": f(outcomes["departures_h"][c["id"]])} for c in decision["cars"]}
    ids = [c["id"] for c in decision["cars"]]
    base = [f(x) for x in decision["base_load_kwh"]]
    cap = [f(decision["connection_kw"])] * T
    delivered = {i: 0.0 for i in ids}; executed = {i: [0.0] * T for i in ids}
    for t in range(T):
        apply_events(decision["events"], cars, cap, t)
        start = t * DT
        active = [i for i in ids if cars[i]["arrival_h"] <= start + 1e-9 and cars[i]["departure_h"] > start
                  and cars[i]["request_kwh"] - delivered[i] > TOL]
        remaining = [cars[i]["request_kwh"] - delivered[i] for i in active]
        if active:
            for i, a in zip(active, allocate(policy, t, [cars[i] for i in active], remaining, base[t], cap[t])):
                got = a * present(cars[i], t); executed[i][t] = got; delivered[i] += got
    return executed, cap, cars


def physical(evidence):
    errors = []
    d, o, rec, res = evidence["decision_inputs"], evidence["outcomes"], evidence["record"], evidence["results"]
    ids = [c["id"] for c in d["cars"]]
    if len(set(ids)) != len(ids):
        errors.append("duplicate car identifiers")
    cars = {c["id"]: {**{k: f(c[k]) for k in ("arrival_h", "request_kwh", "max_kw", "promise_h")}, "id": c["id"],
                      "departure_h": f(o["departures_h"][c["id"]])} for c in d["cars"]}
    cap = [f(d["connection_kw"])] * T
    for e in sorted(d["events"], key=lambda e: int(e["at_slot"])):
        if e["type"] == "cap" and not int(e["at_slot"]) <= int(e["from_slot"]) < int(e["to_slot"]) <= T:
            errors.append("grid request issued after it started")
        if e["type"] == "leave":
            car = cars.get(e["car_id"])
            if car is None:
                errors.append("declared departure for an unknown car")
            elif not car["arrival_h"] <= int(e["at_slot"]) * DT < car["departure_h"] or f(e["departure_h"]) < int(e["at_slot"]) * DT:
                errors.append("declared departure outside the connected period")
    for t in range(T):
        apply_events(d["events"], cars, cap, t)
    if any(abs(a - f(b)) > CHECK_TOL for a, b in zip(cap, rec["cap_kw"])):
        errors.append("recorded cap profile differs from connection plus grid requests")
    base = [f(x) for x in d["base_load_kwh"]]; pv = [f(x) for x in o["pv_outcome_kwh"]]; ci = [f(x) for x in o["ci_actual"]]
    tariff = [f(x) for x in d["tariff"]]
    ev = [0.0] * T; delivered = {}
    for i in ids:
        row = [f(x) for x in rec["executed_kwh"][i]]
        if len(row) != T:
            errors.append("executed record length"); continue
        car = cars[i]
        for t, x in enumerate(row):
            if x < -CHECK_TOL or x > car["max_kw"] * DT + CHECK_TOL:
                errors.append(f"power limit {i} slot {t}")
            if x > CHECK_TOL and not present(car, t):
                errors.append(f"energy to a car that was not connected: {i} slot {t}")
            ev[t] += x
        delivered[i] = sum(row)
        if delivered[i] > car["request_kwh"] + CHECK_TOL:
            errors.append(f"delivered more than requested: {i}")
    envelope = [b + e for b, e in zip(base, ev)]
    for t in range(T):
        if envelope[t] > cap[t] * DT + CHECK_TOL:
            errors.append(f"connection cap exceeded with zero solar at slot {t}")
    imports = [max(0.0, e - p) for e, p in zip(envelope, pv)]
    unserved = {i: max(0.0, cars[i]["request_kwh"] - delivered[i]) for i in ids}
    expected = {"emissions_kgco2": sum(m * c for m, c in zip(imports, ci)) / 1000, "cost_gbp": sum(m * p for m, p in zip(imports, tariff)),
                "peak_import_kw": max(imports) / DT, "unserved_kwh": sum(unserved.values()), "delivered_kwh": sum(delivered.values()),
                "served": sum(u <= SERVED_TOL for u in unserved.values()), "sessions": len(ids)}
    for key, value in expected.items():
        if abs(value - f(res[key])) > 1e-4 * max(1, abs(value)):
            errors.append(f"result arithmetic: {key}")
    for i in ids:
        if abs(unserved[i] - f(res["per_car"][i]["unserved_kwh"])) > CHECK_TOL:
            errors.append(f"per-car shortfall arithmetic: {i}")
    return errors


def decision_replay(evidence):
    policy = evidence["controller"]["policy"]
    if policy not in REPLAYABLE:
        return {"status": "CONSTRAINTS_ONLY", "verified": False, "errors": [],
                "note": "Optimisation decisions are checked against constraints but not re-solved by this stdlib verifier."}
    executed, _, _ = replay(policy, evidence["decision_inputs"], evidence["outcomes"])
    errors = []
    for i, row in executed.items():
        if any(abs(a - f(b)) > CHECK_TOL for a, b in zip(row, evidence["record"]["executed_kwh"][i])):
            errors.append(f"recorded charging differs from the policy re-run for {i}")
    return {"status": "VERIFIED" if not errors else "MISMATCH", "verified": not errors, "errors": errors[:10],
            "note": "Re-run used only plug-in data, requests, promises, events, base load, cap and connection status at each slot start."}


def _grid(root, date):
    anchors = json.loads((root / "data/trust/source_anchors.v1.json").read_text(encoding="utf-8"))["sources"]
    carbon = _load_pinned(None, anchors["neso-national-ci-2025"], root)
    weather = _load_pinned(None, anchors["openmeteo-london-weather-2025"], root)
    if carbon is None or weather is None:
        return None
    ci = {}
    for row in carbon["result"]["records"]:
        ts = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
        ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
        ci[ts] = None if row["actual"] is None else f(row["actual"])
    hourly = weather["hourly"]
    radiation = {datetime.fromisoformat(t).replace(tzinfo=timezone.utc): r for t, r in zip(hourly["time"], hourly["shortwave_radiation"])}
    issue = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    slots = [issue + timedelta(minutes=30 * t) for t in range(T)]
    actual = [ci[s] for s in slots]
    past = sorted((k, v) for k, v in ci.items() if k < issue and v is not None)
    latest = past[-1][1]
    forecast = []
    for s in slots:
        samples = [ci.get(s - timedelta(days=k)) for k in range(1, 8)]
        valid = [x for x in samples if x is not None]
        forecast.append(statistics.median(valid) if valid else latest)
    rad = [radiation[s.replace(minute=0) + timedelta(hours=1)] for s in slots]
    day = issue.timetuple().tm_yday
    daylight = 12 + 4 * math.sin(2 * math.pi * (day - 80) / 365); sunrise = 12 - daylight / 2
    season = .58 + .20 * math.sin(2 * math.pi * (day - 80) / 365)
    hours = [(t + .5) * DT for t in range(T)]
    return {"ci_actual": actual, "ci_forecast": [min(1500.0, max(0.0, x)) for x in forecast],
            "pv_outcome_kwh": [20 * .5 * .8 * min(1, max(0, r / 1000)) for r in rad],
            "pv_forecast_kwh": [20 * .5 * season * max(0, math.sin(math.pi * (h - sunrise) / daylight)) if sunrise <= h <= sunrise + daylight else 0.0 for h in hours],
            "base_load_kwh": [.5 * (6 + 8 * (8 <= h < 18) + 2 * (18 <= h < 22)) for h in hours],
            "tariff": [.12 if h < 7 else .36 if 16 <= h < 20 else .23 for h in hours]}


def _sessions(root, date):
    manifest = json.loads((root / "data/trust/carpark_anchors.v1.json").read_text(encoding="utf-8"))
    anchor = manifest["sources"]["utrecht-workplace-ev-sessions"]
    path = root / anchor["paths"][0]
    if not path.exists():
        return None, "Raw session file not present locally (licence: not redistributed). Run scripts/fetch_workplace_sessions.py."
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != anchor["sha256"]:
        raise ValueError("local session file differs from the trusted digest")
    try:
        from zoneinfo import ZoneInfo
        local = ZoneInfo("Europe/Amsterdam")
    except Exception as exc:  # tzdata unavailable on some systems
        return None, f"Time-zone database unavailable: {exc}"
    shared = {"EV107", "EV191", "EV132", "EV148", "EV342", "EV242", "EV130", "EV173", "EV131", "EV384",
              "EV318", "EV127", "EV257", "EV192", "EV129", "EV211", "EV323", "EV343", "EV161", "EV456"}
    rows = {}
    for row in csv.DictReader(body.decode("utf-8-sig").splitlines(), delimiter=";"):
        if row["rail"] not in manifest["site_transform"]["rails"]:
            continue
        start = datetime.fromisoformat(row["start_datetime"]).replace(tzinfo=local).astimezone(timezone.utc)
        if start.strftime("%Y-%m-%d") != date:
            continue
        end = datetime.fromisoformat(row["end_datetime"]).replace(tzinfo=local).astimezone(timezone.utc)
        sid = hashlib.sha256(f"{row['EV_id_x']}|{start}|{row['evse_uid']}".encode()).hexdigest()[:12]
        midnight = start.replace(hour=0, minute=0, second=0)
        rows[sid] = {"driver": "shared" if row["EV_id_x"] in shared else row["EV_id_x"], "energy_kwh": f(row["total_energy"]),
                     "arrival_h": (start - midnight).total_seconds() / 3600, "departure_h": (end - midnight).total_seconds() / 3600}
    return rows, None


def lineage(evidence, root):
    errors, warnings, checks = [], [], {}
    grid_date = evidence["sources"]["grid"]["grid_date"]
    grid = _grid(root, grid_date)
    d, o = evidence["decision_inputs"], evidence["outcomes"]
    if grid is None:
        checks["grid"] = "NOT_LOCALLY_CHECKED"; warnings.append("Pinned grid snapshots unavailable")
    else:
        for key, recorded in [("ci_forecast", d["ci_forecast"]), ("pv_forecast_kwh", d["pv_forecast_kwh"]), ("base_load_kwh", d["base_load_kwh"]),
                              ("tariff", d["tariff"]), ("ci_actual", o["ci_actual"]), ("pv_outcome_kwh", o["pv_outcome_kwh"])]:
            if any(abs(a - f(b)) > CHECK_TOL for a, b in zip(grid[key], recorded)):
                errors.append(f"grid value does not match pinned source: {key}")
        checks["grid"] = "RECONSTRUCTED" if not errors else "MISMATCH"
    rows, note = _sessions(root, evidence["sources"]["sessions"]["session_date"])
    # Two declared transforms: decision-time (fixed 11 kW, request = session energy, every session kept)
    # and the earlier capped one (power from the session, request capped by the real departure).
    declared = evidence["sources"]["sessions"].get("transform") == "declared-request-fixed-11kw-v1"
    if rows is None:
        checks["sessions"] = "NOT_LOCALLY_CHECKED"; warnings.append(note)
    else:
        session_errors = []
        cars = {c["id"]: c for c in d["cars"]}
        for sid in set(cars) - set(rows):
            session_errors.append(f"car {sid} is not a site session on that date")
        omitted = []
        for sid, row in rows.items():
            dwell = row["departure_h"] - row["arrival_h"]
            probe = {"arrival_h": row["arrival_h"], "departure_h": row["departure_h"],
                     "max_kw": 11.0 if declared else max(11.0, row["energy_kwh"] / max(dwell, 1e-6))}
            asap, remaining = 0.0, row["energy_kwh"]
            for t in range(first_slot(probe), T):
                got = min(probe["max_kw"] * DT, remaining) * present(probe, t); asap += got; remaining -= got
                if remaining <= TOL:
                    break
            car = cars.get(sid)
            if car is None:
                # Completeness: only sessions with nothing servable may be absent (declared transform).
                if declared or min(row["energy_kwh"], asap) > 1e-6:
                    omitted.append(sid)
                continue
            ok = (abs(f(car["arrival_h"]) - row["arrival_h"]) <= 1e-6 and abs(f(o["departures_h"][sid]) - row["departure_h"]) <= 1e-6
                  and car["driver"] == row["driver"] and abs(f(car["max_kw"]) - probe["max_kw"]) <= 1e-6)
            expected_request = row["energy_kwh"] if declared else min(row["energy_kwh"], asap)
            if not ok or abs(f(car["request_kwh"]) - expected_request) > 1e-6:
                session_errors.append(f"car {sid} differs from the pinned session record")
        if omitted:
            session_errors.append(f"{len(omitted)} servable site session(s) on that date are missing from the record, e.g. {omitted[0]}")
        errors += session_errors
        checks["sessions"] = "RECONSTRUCTED" if not session_errors else "MISMATCH"
    verified = not errors and all(v == "RECONSTRUCTED" for v in checks.values())
    return {"status": "VERIFIED" if verified else "MISMATCH" if errors else "INCOMPLETE", "verified": verified,
            "errors": errors[:10], "warnings": warnings, "checks": checks,
            "trust_boundary": "Correspondence with separately pinned download digests and declared transforms. Not proof the upstream measurements are true."}


def inspect(evidence, expected, root):
    root = Path(root)
    levels = {}
    integrity = sha(evidence) == expected.removeprefix("0x").lower()
    levels["integrity"] = {"status": "VERIFIED" if integrity else "MISMATCH", "verified": integrity}
    if evidence.get("schema") != SCHEMA or evidence.get("canonicalization") != "gridproof-canonical-json-v1/float-decimal-strings-9":
        return {"verified": False, "status": "UNSUPPORTED", "levels": levels, "errors": ["unsupported evidence schema"]}
    try:
        phys = physical(evidence)
    except (KeyError, TypeError, ValueError) as exc:
        phys = [f"malformed record: {exc}"]
    levels["physical_service"] = {"status": "VERIFIED" if not phys else "MISMATCH", "verified": not phys, "errors": phys[:10]}
    try:
        levels["decision_replay"] = decision_replay(evidence)
    except (KeyError, TypeError, ValueError) as exc:
        levels["decision_replay"] = {"status": "MISMATCH", "verified": False, "errors": [f"replay failed: {exc}"]}
    try:
        levels["source_lineage"] = lineage(evidence, root)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        levels["source_lineage"] = {"status": "MISMATCH", "verified": False, "errors": [f"lineage failed: {exc}"]}
    required = ["integrity", "physical_service", "source_lineage"] + (["decision_replay"] if levels["decision_replay"]["status"] != "CONSTRAINTS_ONLY" else [])
    verified = all(levels[k]["verified"] for k in required)
    errors = [e for k in levels for e in levels[k].get("errors", [])]
    if not integrity:
        errors.insert(0, "SHA256 does not match the expected digest")
    status = "VERIFIED" if verified else "INCOMPLETE" if not errors else "REJECTED"
    return {"verified": verified, "status": status, "levels": levels, "errors": errors,
            "not_proven": ["physical metering or charger execution", "that the record was committed before the day",
                           "site ownership or global double counting", "causal avoided emissions"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path"); parser.add_argument("--digest"); parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    payload = json.loads(Path(args.path).read_text(encoding="utf-8-sig"))
    evidence = payload.get("evidence", payload)
    expected = args.digest or payload.get("digest")
    if not expected:
        raise SystemExit("--digest required for raw evidence")
    result = inspect(evidence, expected, args.root)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
