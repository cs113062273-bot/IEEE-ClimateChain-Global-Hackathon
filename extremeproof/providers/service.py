"""One simulated independent data provider (run one process per provider).

Environment:
  EP_PROVIDER_SOURCE  which spec source this provider computes from: "station" or "era5"
  EP_PROVIDER_KEY     its own private key (local demo chain only)
  EP_RPC              JSON-RPC URL of the chain (default http://127.0.0.1:8545)
  EP_DEPLOYMENT       path to the deployment JSON written by contracts/scripts/deploy.mjs
  EP_STATE_DIR        where the provider keeps its fetched data and evidence
  EP_DEMO_ATTACKS     "1" enables the /attack endpoint used by the demo

Flow per agreement:
  POST /report {agreement_id, spec, interim: true}
                                     - during the season: fetches the days already published (up to
                                       PUBLICATION_LAG_DAYS ago); if they hold a qualifying spell longer
                                       than the one already on chain, posts those days' readings, so the
                                       contract sees the spell and the share it supports can be released.
  POST /report {agreement_id, spec}  - checks sha256(spec) equals the hash the three parties
                                       approved on chain, waits for the observation window to
                                       end, fetches the observation-year data the spec names and
                                       posts the rest of the season's readings with the sha256 of
                                       its evidence (which names the fetched files). The contract
                                       computes the spell and the verdict from the readings.
  GET  /evidence/{agreement_id}      - the evidence bundle
  GET  /observations/{agreement_id}  - the observation-year files it fetched (base64)

The fetch is simulated: it cuts the season from the pinned October 2026 download
(see climate/archive.py). The readings are public data, so they are not sealed; the
contract enforces who may post, against which signed thresholds, and that days on
chain are never rewritten.
"""
import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3

from datetime import datetime, timedelta

from extremeproof.climate.trigger import (LOCAL_TZ, PUBLICATION_LAG_DAYS, evaluate, evidence_digest, fetch_observations,
                                          spec_hash)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = os.environ.get("EP_PROVIDER_SOURCE", "station")
RPC = os.environ.get("EP_RPC", "http://127.0.0.1:8545")
DEPLOYMENT = Path(os.environ.get("EP_DEPLOYMENT", ROOT / ".runtime" / "deployment.json"))
STATE = Path(os.environ.get("EP_STATE_DIR", ROOT / ".runtime" / "providers" / SOURCE))
ATTACKS = os.environ.get("EP_DEMO_ATTACKS") == "1"
ABI_PATH = ROOT / "contracts" / "artifacts" / "contracts" / "TriggerAgreement.sol" / "TriggerAgreement.json"
STATUS = ["None", "Proposed", "Locked", "Disputed", "Paid", "Refunded", "Cancelled"]
VERDICT_NAME = {1: "met", 2: "not met", 3: "abstain"}
OUTCOME = {0: None, 1: True, 2: False, 3: None}
STATUS_CODE = {"observed": 0, "filled": 1, "missing": 2}  # SeasonRecord day status

app = FastAPI(title=f"ExtremeProof provider ({SOURCE})")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Ctx:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC))
        self.acct = self.w3.eth.account.from_key(os.environ["EP_PROVIDER_KEY"])
        dep = json.loads(DEPLOYMENT.read_text(encoding="utf-8"))
        abi = json.loads(ABI_PATH.read_text(encoding="utf-8"))["abi"]
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(dep["TriggerAgreement"]), abi=abi)
        STATE.mkdir(parents=True, exist_ok=True)

    def send(self, fn):
        tx = fn.build_transaction({"from": self.acct.address, "nonce": self.w3.eth.get_transaction_count(self.acct.address),
                                   "gas": 3_000_000, "chainId": self.w3.eth.chain_id})
        signed = self.acct.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=30)
        if rcpt.status != 1:
            raise HTTPException(409, "transaction reverted")
        return h.hex()


_ctx = None


def ctx():
    global _ctx
    if _ctx is None:
        _ctx = Ctx()
    return _ctx


def state_path(aid):
    return STATE / f"agreement-{aid}.json"


def load_state(aid):
    p = state_path(aid)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_state(aid, st):
    state_path(aid).write_text(json.dumps(st, indent=1), encoding="utf-8")


def revert_reason(e):
    msg = str(e)
    for name in ("NormalMismatch", "AlreadyReported", "FutureDay", "IncompleteSeason", "BadDays", "BadStatus", "NoNormal",
                 "EmptyEvidence", "TooEarly", "TooLate", "NotProvider", "WrongStatus"):
        if name in msg:
            return name
    return msg[:200]


class ReportIn(BaseModel):
    agreement_id: int
    spec: dict
    interim: bool = False


@app.get("/health")
def health():
    c = ctx()
    return {"source": SOURCE, "address": c.acct.address, "contract": c.contract.address, "attacks_enabled": ATTACKS}


@app.post("/report")
def report(body: ReportIn):
    c = ctx()
    aid = body.agreement_id
    ag = c.contract.functions.getAgreement(aid).call()
    on_chain = "0x" + ag[0].hex()
    if spec_hash(body.spec) != on_chain:
        raise HTTPException(400, f"spec hash {spec_hash(body.spec)} differs from the approved hash {on_chain}; refusing")
    if STATUS[ag[6]] != "Locked":
        raise HTTPException(409, f"agreement is {STATUS[ag[6]]}, not Locked")
    if not c.contract.functions.isProvider(aid, c.acct.address).call():
        raise HTTPException(403, "this provider is not part of the agreement")
    assigned = body.spec.get("settlement", {}).get("provider_addresses", {}).get(SOURCE)
    if assigned is not None and assigned != c.acct.address.lower():
        raise HTTPException(403, f"the signed spec assigns the {SOURCE} source to {assigned}, not to this provider")
    window_start, window_end = ag[9][0], ag[9][1]
    now = c.w3.eth.get_block("latest")["timestamp"]
    st = load_state(aid) or {"interim": []}
    if body.interim:
        return interim_report(c, aid, body.spec, st, now, window_start, window_end)
    if now < window_end:
        raise HTTPException(409, f"observation window still open (chain time {now} < {window_end})")
    if "verdict" in st:
        return public(st)
    # The season is over: fetch what the spec names and post the rest of the season's readings.
    fetched = fetch_observations(body.spec, SOURCE)
    ev = evaluate(body.spec, SOURCE, season=fetched)
    ev["fetched_at_chain_time"] = now
    digest = evidence_digest(ev)
    normal, values, status = post_args(c, aid, body.spec, ev)
    tx = c.send(c.contract.functions.postDays(aid, normal, values, status, bytes.fromhex(digest[2:]), True))
    verdict, spell = c.contract.functions.reportOf(aid, c.acct.address).call()
    files = {ev["observations"][sid]["file"]: base64.b64encode(b).decode("ascii") for sid, b in fetched.items()}
    st.update({"verdict": verdict, "outcome": OUTCOME[verdict], "reason": ev["reason"], "longest_spell": spell, "days_posted": len(values),
               "evidence_digest": digest, "report_tx": tx, "evidence": ev, "files": {**st.get("files", {}), **files}})
    if OUTCOME[verdict] != ev["outcome"]:  # the contract and the engine must read the readings the same way
        st["chain_disagrees_with_engine"] = True
    save_state(aid, st)
    return public(st)


def post_args(c, aid, spec, ev):
    """The signed thresholds and the season days not yet on chain, as the contract takes them."""
    normal = next(s for s in spec["sources"] if s["id"] == SOURCE)["season_normal_mdegc"]
    if normal is None:  # no valid normal: the provider can only abstain, with no readings
        return [], [], []
    posted = c.contract.functions.getRecord(aid, c.acct.address).call()[0]
    days = (ev.get("season") or {}).get("days", [])[posted:]
    return normal, [x["v"] if x["v"] is not None else 0 for x in days], [STATUS_CODE[x["status"]] for x in days]


def interim_report(c, aid, spec, st, now, window_start, window_end):
    """During the season: post the days already published if they hold a longer qualifying spell than the chain shows."""
    if not window_start <= now < window_end:
        raise HTTPException(409, "interim reports are only accepted during the season")
    through = (datetime.fromtimestamp(now, LOCAL_TZ) - timedelta(days=PUBLICATION_LAG_DAYS)).date()
    fetched = fetch_observations(spec, SOURCE, through=through)
    ev = evaluate(spec, SOURCE, season=fetched, through=through)
    ev["fetched_at_chain_time"] = now
    spell = min(int((ev.get("season") or {}).get("longest_spell", 0)), 65535)
    on_chain = c.contract.functions.getRecord(aid, c.acct.address).call()[2]
    out = {"through": through.isoformat(), "longest_spell": spell, "outcome": ev["outcome"], "reported": False}
    if ev["outcome"] is not True or spell <= on_chain:
        return out  # nothing new to claim: no qualifying spell yet, or not longer than the one on chain
    n = len(st["interim"]) + 1
    for o in ev["observations"].values():  # the evidence names the paths its files have in the bundle
        o["file"] = f"observations/{SOURCE}/interim-{n}/{o['file'].rsplit('/', 1)[1]}"
    files = {o["file"]: base64.b64encode(fetched[sid]).decode("ascii") for sid, o in ev["observations"].items()}
    digest = evidence_digest(ev)
    normal, values, status = post_args(c, aid, spec, ev)
    tx = c.send(c.contract.functions.postDays(aid, normal, values, status, bytes.fromhex(digest[2:]), False))
    st["interim"].append({"longest_spell": spell, "through": through.isoformat(), "days_posted": len(values), "evidence_digest": digest,
                          "report_tx": tx, "evidence": ev, "files": files})
    save_state(aid, st)
    return {**out, "reported": True, "days_posted": len(values), "evidence_digest": digest, "report_tx": tx}


@app.post("/attack/{agreement_id}")
def attack(agreement_id: int):
    """Demo only: after seeing the other report, try to lower the signed "unusually hot" line by 2 degrees
    and post a hotter season. The contract must refuse: the thresholds are fixed by the signed fingerprint."""
    if not ATTACKS:
        raise HTTPException(404)
    c = ctx()
    st = load_state(agreement_id)
    if not st or "verdict" not in st:
        raise HTTPException(409, "report first")
    spec_normal = (st["evidence"].get("season_normal_mdegc") or [])
    lowered = [t - 2000 for t in spec_normal]
    days = (st["evidence"].get("season") or {}).get("days", [])
    try:
        c.send(c.contract.functions.postDays(agreement_id, lowered, [x["v"] or 0 for x in days], [STATUS_CODE[x["status"]] for x in days],
                                             bytes.fromhex(st["evidence_digest"][2:]), True))
    except Exception as e:  # noqa: BLE001
        return {"attempted": "post the season again against a normal 2 degC lower, after seeing the other report", "accepted": False,
                "reason": revert_reason(e)}
    return {"attempted": "lowered normal", "accepted": True}


def public(st):
    keys = ("verdict", "outcome", "reason", "longest_spell", "days_posted", "evidence_digest", "report_tx")
    return {k: st[k] for k in keys if k in st}


@app.get("/evidence/{agreement_id}")
def evidence(agreement_id: int):
    st = load_state(agreement_id)
    if not st or not (st.get("evidence") or st.get("interim")):
        raise HTTPException(404, "evidence is published with the report")
    standing = st.get("evidence") or st["interim"][-1]["evidence"]
    standing_digest = st.get("evidence_digest") or st["interim"][-1]["evidence_digest"]
    # the standing report's evidence is the bundle's main evidence; earlier interim reports go alongside
    interim = [x["evidence"] for x in st.get("interim", []) if x["evidence_digest"] != standing_digest]
    return {"provider": public(st), "evidence": standing, "interim": interim}


@app.get("/observations/{agreement_id}")
def observations(agreement_id: int):
    st = load_state(agreement_id)
    if not st:
        raise HTTPException(404, "nothing fetched for this agreement")
    files = dict(st.get("files", {}))
    for x in st.get("interim", []):
        files.update(x["files"])
    return files


@app.post("/reset")
def reset():
    """Demo only: forget reports and fetched data after the hub rolls the chain back."""
    if not ATTACKS:
        raise HTTPException(404)
    for f in STATE.glob("agreement-*.json"):
        f.unlink()
    return {"reset": True}
