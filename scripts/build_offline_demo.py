"""Package a self-contained, dependency-free browser replay; never publish it."""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    demo=json.loads((ROOT/"data/sample/demo.json").read_text(encoding="utf-8"))
    proof=json.loads((ROOT/"data/sample/evidence.json").read_text(encoding="utf-8"))
    proof.pop("canonical_json",None)
    if proof["evidence"]["schema_version"]!="2.0.0":raise ValueError("A current v2 proof is required")
    benchmark=ROOT/"experiments/competition_v2/summary.json"
    payload={"runs":demo["runs"],"proof":proof,"anchors":json.loads((ROOT/"data/trust/source_anchors.v1.json").read_text(encoding="utf-8")),"benchmark":json.loads(benchmark.read_text(encoding="utf-8")) if benchmark.exists() else None}
    template=(ROOT/"frontend/components/offline-template.html").read_text(encoding="utf-8")
    body=json.dumps(payload,separators=(",",":"),ensure_ascii=True).replace("<","\\u003c")
    output=ROOT/"offline/index.html";output.parent.mkdir(exist_ok=True)
    output.write_text(template.replace("__GRIDPROOF_DATA__",body),encoding="utf-8")
    public=ROOT/"frontend/public/offline/index.html";public.parent.mkdir(parents=True,exist_ok=True)
    public.write_bytes(output.read_bytes())
    print(json.dumps({"path":"offline/index.html","bytes":output.stat().st_size,"dates":[r["date"] for r in demo["runs"]],"network_required":False,"chain_status":"NOT CHECKED; recorded local receipts are not live-chain proof"}))

if __name__=="__main__":main()
