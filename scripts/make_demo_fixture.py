from __future__ import annotations
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app.domain.schemas import OptimizeRequest
from backend.app.services.data import ROOT,available_dates
from backend.app.services.simulator import compare
from backend.app.services.evidence import make_evidence

def main():
    runs=[compare(OptimizeRequest(date=date)) for date in available_dates()]
    if len(runs)<2:raise ValueError("Two authentic sourced windows required")
    value={"schema_version":"1.0.0","mode":"offline historical replay using downloaded official sources and modeled facility","runs":runs}
    output=ROOT/"data/sample/demo.json";output.write_text(json.dumps(value,indent=2),encoding="utf-8")
    evidence=make_evidence(runs[-1]["run_id"])
    (ROOT/"data/sample/evidence.json").write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"path":str(output),"run_ids":[r["run_id"] for r in runs],"evidence_id":evidence["evidence_id"],"digest":evidence["digest"]}))
if __name__=="__main__":main()
