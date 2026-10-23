"""Drive one agreement through its whole life against a running stack (headless demo).

    extremeproof/.venv/Scripts/python -m extremeproof.scripts.demo_flow --site antalya --year 2024

Parties sign with their demo keys, the chain clock is advanced past the season,
each provider fetches the season and files one report through its own service,
anyone finalizes,
and the hub runs the independent verifier on the result.
"""
import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

from web3 import Web3

from extremeproof.climate.specs import make_spec
from extremeproof.climate.trigger import spec_hash

ROOT = Path(__file__).resolve().parents[1]
ABI = json.loads((ROOT / "contracts" / "artifacts" / "contracts" / "TriggerAgreement.sol" / "TriggerAgreement.json").read_text())["abi"]
TOKEN_ABI = json.loads((ROOT / "contracts" / "artifacts" / "contracts" / "DemoToken.sol" / "DemoToken.json").read_text())["abi"]
STATUS = ["None", "Proposed", "Locked", "Disputed", "Paid", "Refunded", "Cancelled"]
FALLBACK = {"refund": 0, "pay": 1}


def http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as f:
            return json.loads(f.read())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "detail": json.loads(e.read() or b"{}").get("detail")}


class Demo:
    def __init__(self, rpc, hub, deployment):
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        self.hub = hub
        self.dep = deployment
        self.c = self.w3.eth.contract(address=Web3.to_checksum_address(deployment["TriggerAgreement"]), abi=ABI)
        self.token = self.w3.eth.contract(address=Web3.to_checksum_address(deployment["DemoToken"]), abi=TOKEN_ABI)
        self.keys = deployment["demoKeys"]
        self.providers = {p["source"]: p for p in http("GET", f"{hub}/api/deployment")["providers"]}

    def send(self, role, fn):
        acct = self.w3.eth.account.from_key(self.keys[role])
        tx = fn.build_transaction({"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address),
                                   "gas": 1_500_000, "chainId": self.w3.eth.chain_id})
        h = self.w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        r = self.w3.eth.wait_for_transaction_receipt(h)
        if r.status != 1:
            raise RuntimeError(f"{role} transaction reverted")
        return r

    def now(self):
        return self.w3.eth.get_block("latest")["timestamp"]

    def warp(self, ts):
        if ts > self.now():
            self.w3.provider.make_request("evm_setNextBlockTimestamp", [ts])
            self.w3.provider.make_request("evm_mine", [])

    def spec(self, **kw):
        """A spec naming this deployment's parties, providers, token and contract (what the UI signs)."""
        return make_spec(parties=self.dep["roles"], providers={k: v["address"] for k, v in self.providers.items()},
                         token=self.dep["DemoToken"], contract=self.dep["TriggerAgreement"],
                         chain_id=self.w3.eth.chain_id, **kw)

    def propose_and_lock(self, spec, override=None):
        """Propose exactly what the spec says; ``override`` (tests only) makes the chain disagree with the text."""
        reg = http("POST", f"{self.hub}/api/specs", {"spec": spec})
        h = reg["hash"]
        assert h == spec_hash(spec)
        st = spec["settlement"]
        roles = {k: v.lower() for k, v in self.dep["roles"].items()}
        roles.update(st.get("parties", {}))
        prov = st.get("provider_addresses") or {k: v["address"] for k, v in self.providers.items()}
        t = st["timing"]
        args = {
            "parties": tuple(Web3.to_checksum_address(roles[k]) for k in ("funder", "community", "checker", "beneficiary")),
            "token": self.token.address,
            "amount": st["amount_cents"],
            "providers": [Web3.to_checksum_address(prov["station"]), Web3.to_checksum_address(prov["era5"])],
            "normals": [bytes.fromhex(st["normal_keccak"][k][2:]) for k in ("station", "era5")],
            "quorum": st["quorum"],
            "on_dispute": FALLBACK[st["on_dispute"]],
            "timing": (t["window_start"], t["window_end"], t["report_deadline"], t["dispute_window"]),
            "limits": ((t["window_end"] - t["window_start"]) // 86400, spec["rule"]["max_missing_days"], spec["rule"]["max_filled_days"]),
            "ladder": [tuple(r) for r in st["payout_ladder"]],
        }
        args.update(override or {})
        fn = self.c.functions.propose(bytes.fromhex(h[2:]), args["parties"], args["token"], args["amount"],
                                      args["providers"], args["normals"], args["quorum"], args["on_dispute"], args["timing"],
                                      args["limits"], args["ladder"])
        aid = self.c.functions.nextId().call()
        self.send("funder", fn)
        for role in ("funder", "community", "checker"):
            self.send(role, self.c.functions.approve(aid, bytes.fromhex(h[2:])))
        return aid, t

    def report_round(self, aid, spec, t, attack=False):
        """After the season every provider reports once (an abstention is a report); then anyone finalizes."""
        self.warp(t["window_end"])
        out = {}
        for src, p in self.providers.items():
            out[src] = http("POST", f"{p['url']}/report", {"agreement_id": aid, "spec": spec})
        if attack:
            out["attack"] = http("POST", f"{self.providers['era5']['url']}/attack/{aid}")
        self.send("checker", self.c.functions.finalize(aid))
        out["status"] = STATUS[self.c.functions.getAgreement(aid).call()[6]]
        return out

    def interim_round(self, aid, spec, ts):
        """During the season at chain time ts: each provider reports a spell already seen; anyone releases."""
        self.warp(ts)
        out = {src: http("POST", f"{p['url']}/report", {"agreement_id": aid, "spec": spec, "interim": True})
               for src, p in self.providers.items()}
        try:
            self.send("checker", self.c.functions.release(aid))
            out["released"] = True
        except Exception:  # noqa: BLE001  NothingToRelease: no quorum-supported share beyond what was released
            out["released"] = False
        return out

    def status(self, aid):
        return STATUS[self.c.functions.getAgreement(aid).call()[6]]

    def balance(self, role):
        return self.token.functions.balanceOf(self.dep["roles"][role]).call()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="antalya")
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--base", default="1991-2020")
    ap.add_argument("--fill", default="era5_quantile_map")
    ap.add_argument("--rpc", default="http://127.0.0.1:8545")
    ap.add_argument("--hub", default="http://127.0.0.1:8600")
    a = ap.parse_args()
    dep = json.loads((ROOT / ".runtime" / "deployment.json").read_text())
    d = Demo(a.rpc, a.hub, dep)
    b0, b1 = map(int, a.base.split("-"))
    spec = d.spec(site=a.site, year=a.year, base=(b0, b1), fill_method=a.fill)
    aid, t = d.propose_and_lock(spec)
    print("agreement", aid, "locked; spec", spec_hash(spec))
    res = d.report_round(aid, spec, t, attack=True)
    print(json.dumps(res, indent=1))
    print(json.dumps(http("POST", f"{a.hub}/api/verify/{aid}"), indent=1)[:3000])


if __name__ == "__main__":
    main()
