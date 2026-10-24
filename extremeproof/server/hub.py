"""Demo hub: spec registry, verification bundles and verifier runs.

The hub holds no authority. Specs are stored by their sha256 (anyone can check
them against the chain), bundles are assembled from public material (chain
state, raw files, provider evidence) and the verifier it runs is the same
standalone script included in every bundle.

Environment:
  EP_RPC        JSON-RPC URL (default http://127.0.0.1:8545)
  EP_DEPLOYMENT deployment JSON (default extremeproof/.runtime/deployment.json)
  EP_PROVIDERS  comma list of provider service URLs (default :8601,:8602)
"""
import base64
import csv
import importlib.util
import io
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from web3 import Web3

from extremeproof.climate import archive
from extremeproof.climate.specs import make_spec
from extremeproof.climate.trigger import SpecError, canonical, spec_hash, validate

ROOT = Path(__file__).resolve().parents[1]
RPC = os.environ.get("EP_RPC", "http://127.0.0.1:8545")
DEPLOYMENT = Path(os.environ.get("EP_DEPLOYMENT", ROOT / ".runtime" / "deployment.json"))
PROVIDERS = os.environ.get("EP_PROVIDERS", "http://127.0.0.1:8601,http://127.0.0.1:8602").split(",")
SPECS = ROOT / ".runtime" / "specs"
ABI_PATH = ROOT / "contracts" / "artifacts" / "contracts" / "TriggerAgreement.sol" / "TriggerAgreement.json"
VERIFIER = ROOT / "verifier" / "verify.py"
TAMPERS = ("none", "spec_base_period", "observation", "evidence_outcome", "drop_evidence")
SNAPSHOT_FILE = DEPLOYMENT.parent / "chain-snapshot.json"

_spec = importlib.util.spec_from_file_location("ep_verify", VERIFIER)
verify_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_mod)

app = FastAPI(title="ExtremeProof hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def chain():
    w3 = Web3(Web3.HTTPProvider(RPC))
    dep = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    abi = json.loads(ABI_PATH.read_text(encoding="utf-8"))["abi"]
    return w3, dep, w3.eth.contract(address=Web3.to_checksum_address(dep["TriggerAgreement"]), abi=abi)


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as f:
        return json.loads(f.read())


class SpecIn(BaseModel):
    spec: dict


@app.get("/api/health")
def health():
    return {"ok": True, "deployment": DEPLOYMENT.exists()}


@app.get("/api/deployment")
def deployment():
    if not DEPLOYMENT.exists():
        raise HTTPException(503, "chain not deployed yet")
    dep = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
    art = ROOT / "contracts" / "artifacts" / "contracts"
    dep["abi"] = {n: json.loads((art / f"{n}.sol" / f"{n}.json").read_text(encoding="utf-8"))["abi"]
                  for n in ("TriggerAgreement", "DemoToken")}
    dep["providers"] = []
    for url in PROVIDERS:
        try:
            h = get_json(url + "/health")
            dep["providers"].append({"url": url, "source": h["source"], "address": h["address"]})
        except OSError:
            dep["providers"].append({"url": url, "error": "unreachable"})
    return dep


class TemplateIn(BaseModel):
    site: str
    year: int
    base: str  # "1961-1990" | "1991-2020"
    percentile: int = 90
    min_spell_days: int = 6
    fill_method: str = "era5_quantile_map"
    max_missing_days: int = 0
    max_filled_days: int = 122
    on_dispute: str = "refund"
    payout: str = "flat"  # "flat" (all or nothing) | "graded"
    payout_steps: list[list[int]] | None = None  # graded rungs: [days beyond the minimum spell, basis points]
    purpose: dict | None = None


@app.post("/api/spec-template")
def spec_template(body: TemplateIn):
    """Build the canonical spec the parties will sign (single source of truth: climate/specs.py)."""
    b0, b1 = (int(x) for x in body.base.split("-"))
    try:
        w3, dep, _ = chain()
        providers = {}
        for url in PROVIDERS:
            h = get_json(url + "/health")
            providers[h["source"]] = h["address"]
        spec = make_spec(site=body.site, year=body.year, base=(b0, b1), percentile=body.percentile,
                         min_spell_days=body.min_spell_days, fill_method=body.fill_method,
                         max_missing_days=body.max_missing_days, max_filled_days=body.max_filled_days,
                         on_dispute=body.on_dispute, parties=dep["roles"], providers=providers, purpose=body.purpose,
                         payout=body.payout, payout_steps=body.payout_steps,
                         token=dep["DemoToken"], contract=dep["TriggerAgreement"], chain_id=w3.eth.chain_id)
        validate(spec)
    except (SpecError, KeyError, ValueError) as e:
        raise HTTPException(400, f"invalid rule: {e}") from e
    return {"spec": spec, "hash": spec_hash(spec), "canonical": canonical(spec).decode("utf-8")}


@app.post("/api/specs")
def put_spec(body: SpecIn):
    try:
        validate(body.spec)
    except (SpecError, KeyError) as e:
        raise HTTPException(400, f"invalid spec: {e}") from e
    h = spec_hash(body.spec)
    SPECS.mkdir(parents=True, exist_ok=True)
    (SPECS / f"{h}.json").write_bytes(canonical(body.spec))
    return {"hash": h, "canonical": canonical(body.spec).decode("utf-8")}


@app.get("/api/specs/{h}")
def get_spec(h: str):
    p = SPECS / f"{h}.json"
    if not p.exists():
        raise HTTPException(404, "unknown spec")
    return json.loads(p.read_bytes())


def snapshot(contract, aid):
    ag = contract.functions.getAgreement(aid).call()
    providers = contract.functions.providersOf(aid).call()
    reports = {}
    for p in providers:
        r = contract.functions.getRecord(aid, p).call()
        verdict, spell = contract.functions.reportOf(aid, p).call()
        # what the contract computed from the provider's posted readings, and the record they left
        reports[p.lower()] = {"verdict": verdict, "longest_spell": spell, "posted": r[0], "run": r[1], "longest": r[2],
                              "filled": r[3], "missing": r[4], "is_final": r[5], "updated_at": r[6], "day_log": "0x" + r[7].hex(),
                              "evidence_digest": "0x" + r[8].hex(), "normal": "0x" + contract.functions.normalOf(aid, p).call().hex()}
    t = ag[9]
    # same keys and layout as verifier/verify.py Chain.agreement, so a snapshot can be compared with the live chain
    agreement = {"spec_hash": "0x" + ag[0].hex(), "funder": ag[1][0].lower(), "community": ag[1][1].lower(),
                 "checker": ag[1][2].lower(), "beneficiary": ag[1][3].lower(), "token": ag[2].lower(),
                 "amount": ag[3], "quorum": ag[4], "on_dispute": ag[5], "status": ag[6], "approvals": ag[7],
                 "timing": {"window_start": t[0], "window_end": t[1], "report_deadline": t[2], "dispute_window": t[3]},
                 "dispute_ends_at": ag[10], "paid_out": ag[11], "contested": ag[12],
                 "limits": {"season_days": ag[13][0], "max_missing": ag[13][1], "max_filled": ag[13][2]},
                 "ladder": [[r[0], r[1]] for r in contract.functions.ladderOf(aid).call()],
                 "providers": [p.lower() for p in providers],
                 "votes_pay": contract.functions.disputeVotesPay(aid).call(),
                 "votes_refund": contract.functions.disputeVotesRefund(aid).call()}
    # every post of readings, in chain order; the verifier compares this list with eth_getLogs
    events = [{"provider": e["args"]["provider"].lower(), "from_day": e["args"]["fromDay"], "count": e["args"]["count"],
               "longest_spell": e["args"]["longestSpell"], "filled": e["args"]["filled"], "missing": e["args"]["missing"],
               "evidence_digest": "0x" + e["args"]["evidenceDigest"].hex(), "is_final": e["args"]["isFinal"]}
              for e in contract.events.DaysPosted().get_logs(from_block=0, argument_filters={"agreementId": aid})]
    return agreement, [p.lower() for p in providers], reports, events


@app.get("/api/agreements/{aid}/resume")
def resume_agreement(aid: int):
    """Read-only recovery. Browser storage is only a pointer, never the money or verdict."""
    if aid < 1:
        raise HTTPException(404, "unknown agreement")
    w3, dep, contract = chain()
    if aid >= contract.functions.nextId().call():
        raise HTTPException(404, "agreement no longer exists; the demo chain may have been reset")
    agreement, _, reports, _ = snapshot(contract, aid)
    spec = get_spec(agreement["spec_hash"])
    providers = {}
    warnings = []
    for url in PROVIDERS:
        try:
            h = get_json(url + "/health")
            r = reports.get(h["address"].lower())
            if not r:
                continue
            entry = {}
            if r["is_final"]:
                entry["report"] = {"verdict": r["verdict"], "outcome": {1: True, 2: False}.get(r["verdict"]),
                                   "reason": "", "longest_spell": r["longest_spell"],
                                   "evidence_digest": r["evidence_digest"]}
            if r["posted"] or r["is_final"]:
                try:
                    ev = get_json(f"{url}/evidence/{aid}")["evidence"]
                    if "0x" + verify_mod.sha256_hex(verify_mod.canonical(ev)) != r["evidence_digest"]:
                        raise ValueError("provider evidence fingerprint differs from the chain")
                    entry["evidence"] = ev
                    if "report" in entry:
                        entry["report"]["reason"] = ev.get("reason", "")
                except (OSError, ValueError) as e:
                    entry["error"] = f"Evidence unavailable: {e}. Reload to retry before verification."
            providers[h["source"]] = entry
        except OSError:
            warnings.append(f"Provider at {url} is unavailable; retry recovery when it is running.")

    events = []
    for abi in contract.abi:
        if abi.get("type") != "event":
            continue
        key = next((x["name"] for x in abi["inputs"] if x["name"] in ("id", "agreementId")), None)
        if key:
            events.extend(contract.events[abi["name"]]().get_logs(from_block=0, argument_filters={key: aid}))
    events.sort(key=lambda e: (e["blockNumber"], e["logIndex"]))
    grouped = {}
    releases = []
    for event in events:
        tx = "0x" + event["transactionHash"].hex()
        entry = grouped.setdefault(tx, {"events": [], "text": []})
        name, a = event["event"], event["args"]
        entry["events"].append(name)
        if name == "DaysPosted":
            entry["text"].append(f"Provider posted {a['count']} days; contract hot spell {a['longestSpell']} days")
        elif name == "Settled":
            entry["text"].append(f"{'During season' if a['how'] == 3 else 'Settlement'}: {a['paid'] / 100:,.2f} DEMO paid, {a['refunded'] / 100:,.2f} returned")
        else:
            entry["text"].append(name)
    log = []
    for tx, entry in grouped.items():
        receipt = w3.eth.get_transaction_receipt(tx)
        timestamp = w3.eth.get_block(receipt["blockNumber"])["timestamp"]
        log.append({"t": timestamp, "text": "; ".join(entry["text"]),
                    "tx": {"hash": tx, "block": receipt["blockNumber"], "gas": receipt["gasUsed"], "events": entry["events"]}})
    for event in events:
        if event["event"] == "Settled" and event["args"]["how"] == 3:
            timestamp = w3.eth.get_block(event["blockNumber"])["timestamp"]
            releases.append({"date": datetime.fromtimestamp(timestamp, timezone(timedelta(hours=3))).date().isoformat(),
                             "amount": str(event["args"]["paid"])})
    return {"spec": spec, "hash": agreement["spec_hash"], "providers": providers, "log": log,
            "releases": releases, "warnings": warnings, "chain_id": w3.eth.chain_id, "contract": dep["TriggerAgreement"]}


def build_bundle(aid):
    """Return {relative path: bytes} for agreement ``aid``."""
    w3, dep, contract = chain()
    agreement, providers, reports, events = snapshot(contract, aid)
    spec_path = SPECS / f"{agreement['spec_hash']}.json"
    if not spec_path.exists():
        raise HTTPException(404, "spec for this agreement is not in the registry")
    spec = json.loads(spec_path.read_bytes())
    files = {"spec.json": canonical(spec)}
    for s in spec["sources"]:  # what the parties pinned at signing
        files[s["history"]["file"]] = archive.read_logical(ROOT, s["history"]["file"])
    by_addr = {}
    for url in PROVIDERS:
        try:
            h = get_json(url + "/health")
            by_addr[h["address"].lower()] = (url, h["source"])
        except OSError:
            continue
    entries = []
    for addr in providers:
        url, source = by_addr.get(addr, (None, None))
        entry = {"address": addr, "source_id": source}
        if url:
            try:
                ev = get_json(f"{url}/evidence/{aid}")
                name = f"evidence/{source}.json"
                files[name] = canonical(ev["evidence"])
                entry["evidence"] = name
                entry["interim"] = []
                for i, iev in enumerate(ev.get("interim", []), start=1):
                    iname = f"evidence/{source}-interim-{i}.json"
                    files[iname] = canonical(iev)
                    entry["interim"].append(iname)
                # what this provider fetched after the season; its evidence (digest on chain) names each file's sha256
                for path, b64 in get_json(f"{url}/observations/{aid}").items():
                    files[path] = base64.b64decode(b64)
            except OSError:
                entry["evidence"] = None
        entries.append(entry)
    bundle = {
        "schema": "extremeproof.bundle.v1",
        "chain": {"chain_id": w3.eth.chain_id, "contract": dep["TriggerAgreement"].lower(), "agreement_id": aid, "rpc_hint": RPC},
        "providers": [e for e in entries if e.get("evidence")],
        "providers_without_evidence": [e for e in entries if not e.get("evidence")],
        "chain_snapshot": {"agreement": agreement, "reports": reports, "events": events},
    }
    files["bundle.json"] = json.dumps(bundle, indent=2).encode("utf-8")
    files["verify.py"] = VERIFIER.read_bytes()
    files["README.txt"] = (
        "ExtremeProof verification bundle\n\n"
        "Recompute the verdict from the raw data and check it against the chain:\n"
        "  python verify.py .                 (offline, uses chain_snapshot in bundle.json)\n"
        f"  python verify.py . --rpc {RPC}   (also re-reads the live chain)\n"
        "  python verify.py . --refetch       (also downloads the season again from each publisher\n"
        "                                      and compares the values; shows what is published today)\n\n"
        "history/       data pinned by sha256 in the signed spec, before the season\n"
        "observations/  what each provider fetched after the season; sha256 in its evidence,\n"
        "               whose digest the provider reported on chain\n"
        "verify.py uses only the Python standard library.\n"
    ).encode("utf-8")
    return files


def tamper(files, kind):
    if kind == "none":
        return "untouched"
    spec = json.loads(files["spec.json"])
    if kind == "spec_base_period":
        old = spec["rule"]["base_period"]
        spec["rule"]["base_period"] = ["1991-01-01", "2020-12-31"] if old[0].startswith("1961") else ["1961-01-01", "1990-12-31"]
        files["spec.json"] = canonical(spec)
        return f"changed the base period after the fact: {old} -> {spec['rule']['base_period']}"
    if kind == "observation":
        # Edit one season reading in the data a provider fetched after the season.
        season_start = f"{spec['observation_year']}-{spec['rule']['season'][0]}"
        season_end = f"{spec['observation_year']}-{spec['rule']['season'][1]}"
        station_obs = next((n for n in files if n.startswith("observations/station/") and n.endswith(".csv")), None)
        if station_obs:
            lines = files[station_obs].decode("utf-8").splitlines(keepends=True)
            header = next(csv.reader([lines[0]]))
            k = header.index("TMAX")
            for i, line in enumerate(lines[1:], start=1):
                row = next(csv.reader([line]))
                if season_start <= row[1] <= season_end and row[k].strip():
                    before = int(row[k]) / 10
                    row[k] = " 450"
                    out = io.StringIO()
                    csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator=line[len(line.rstrip("\r\n")):] or "\n").writerow(row)
                    lines[i] = out.getvalue()
                    files[station_obs] = "".join(lines).encode("utf-8")
                    return f"edited one reading the station provider fetched: {row[1]} TMAX {before} -> 45.0 degC"
        # The station reported nothing this season: edit the ERA5 data the ERA5 provider fetched instead.
        name = next(n for n in files if n.startswith("observations/era5/"))
        doc = json.loads(files[name])
        i = doc["daily"]["time"].index(season_start)
        before = doc["daily"]["temperature_2m_max"][i]
        doc["daily"]["temperature_2m_max"][i] = 45.0
        files[name] = json.dumps(doc).encode("utf-8")
        return f"edited one reading the ERA5 provider fetched: {season_start} {before} -> 45.0 degC (the station has no readings this season)"
    if kind == "drop_evidence":
        bundle = json.loads(files["bundle.json"])
        for name in [n for n in files if n.startswith("evidence/")]:
            del files[name]
        bundle["providers"] = []
        files["bundle.json"] = json.dumps(bundle, indent=2).encode("utf-8")
        return "removed every provider's evidence from the bundle"
    if kind == "evidence_outcome":
        name = next(n for n in files if n.startswith("evidence/"))
        ev = json.loads(files[name])
        ev["outcome"] = not ev["outcome"] if ev.get("outcome") is not None else True
        files[name] = canonical(ev)
        return f"flipped the verdict in {name} to {ev['outcome']}"
    raise HTTPException(400, f"unknown tamper {kind}")


def simulated_publisher(src):
    """What the publisher serves today for a spec source: in this demo, the pinned October 2026 download."""
    return (ROOT / archive.raw_file(src["kind"], src["station"])).read_bytes()


simulated_publisher.label = "simulated publisher: the pinned October 2026 download"


@app.get("/api/bundle/{aid}")
def bundle_zip(aid: int):
    files = build_bundle(aid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(f"extremeproof-agreement-{aid}/{name}", data)
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="extremeproof-agreement-{aid}.zip"'})


@app.post("/api/verify/{aid}")
def run_verifier(aid: int, tamper_kind: str = "none", live: bool = True):
    if tamper_kind not in TAMPERS:
        raise HTTPException(400, f"tamper must be one of {TAMPERS}")
    files = build_bundle(aid)
    what = tamper(files, tamper_kind)
    tmp = Path(tempfile.mkdtemp(prefix="ep-verify-"))
    try:
        for name, data in files.items():
            p = tmp / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        # offline = exactly what `python verify.py bundle` does: no chain, no publisher comparison
        checks = verify_mod.verify(str(tmp), RPC if live else None, publisher=simulated_publisher if live else None)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"tamper": tamper_kind, "what_was_changed": what, "passed": all(c["ok"] for c in checks), "checks": checks}


@app.post("/api/reset")
def reset_chain():
    """Demo only: roll the local chain back to just after deployment (1 May 2021) and clear provider state."""
    w3, dep, _ = chain()
    snap = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))["id"] if SNAPSHOT_FILE.exists() else dep.get("snapshot")
    if not snap or not w3.provider.make_request("evm_revert", [snap]).get("result"):
        raise HTTPException(409, "no snapshot to roll back to; restart the stack")
    new = w3.provider.make_request("evm_snapshot", [])["result"]
    SNAPSHOT_FILE.write_text(json.dumps({"id": new}), encoding="utf-8")
    for url in PROVIDERS:
        req = urllib.request.Request(url + "/reset", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10):
            pass
    return {"reset": True, "chain_time": w3.eth.get_block("latest")["timestamp"]}
