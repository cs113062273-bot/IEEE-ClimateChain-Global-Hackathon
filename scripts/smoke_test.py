from __future__ import annotations
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app.main import app

def main():
    client=TestClient(app)
    health=client.get("/api/health");assert health.status_code==200 and health.json()["fixture_status"]=="ready"
    result=client.post("/api/compare",json={"date":"2025-08-12"});assert result.status_code==200,result.text
    value=result.json()
    assert all(plan["constraints"]["verified"] for plan in value["plans"].values())
    proof=client.post("/api/evidence",json={"run_id":value["run_id"]});assert proof.status_code==200,proof.text
    evidence=proof.json()
    verified=client.post("/api/verify",json={"evidence":evidence["evidence"],"expected_digest":evidence["digest"]});assert verified.json()["verified"],verified.text
    print(json.dumps({"health":"ready","run_id":value["run_id"],"policies":{k:p["metrics"] for k,p in value["plans"].items()},"evidence_sha256":evidence["sha256"],"verification":verified.json()["status"]},indent=2))
if __name__=="__main__":main()
