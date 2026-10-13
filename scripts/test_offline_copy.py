"""Check the shipped source/sample in an isolated copy with network denied.

Uses the current installed Python dependencies; does not claim a new dependency
installation. Bulk files, trained model, runtime runs and chain state are absent.
"""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    runtime=ROOT/".runtime";runtime.mkdir(exist_ok=True)
    if ROOT.resolve() not in runtime.resolve().parents: raise ValueError("Runtime path escapes workspace")
    destination=Path(tempfile.mkdtemp(prefix="offline-source-",dir=runtime))
    if runtime.resolve() not in destination.resolve().parents: raise ValueError("Copy path escapes runtime")
    for folder in ["backend","scripts","data/sample","data/manifests"]:
        shutil.copytree(ROOT/folder,destination/folder,ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(ROOT/"requirements.txt",destination/"requirements.txt")
    shutil.copy2(ROOT/"requirements.lock.txt",destination/"requirements.lock.txt")
    probe=r'''
import json,sys
from pathlib import Path
def deny_network(event,args):
    if event in ("socket.connect","socket.connect_ex"):
        address=args[1]
        if isinstance(address,tuple) and address[0] in ("127.0.0.1","::1"): return
        raise RuntimeError("External network is disabled in the offline source-copy test")
    if event=="socket.getaddrinfo" and args[0] not in ("127.0.0.1","::1","localhost"):
        raise RuntimeError("External DNS is disabled in the offline source-copy test")
sys.addaudithook(deny_network)
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.data import ROOT
from scripts.verify_evidence import inspect
assert not (ROOT/"data/raw").exists()
assert not (ROOT/"data/processed").exists()
assert not (ROOT/"experiments/models").exists()
client=TestClient(app)
health=client.get("/api/health");assert health.status_code==200 and health.json()["fixture_status"]=="ready"
dates=client.get("/api/scenarios").json()["available_dates"]
assert len(dates)>=2
runs=[]
for date in dates:
    result=client.post("/api/compare",json={"date":date});assert result.status_code==200,result.text
    run=result.json();assert all(p["constraints"]["verified"] for p in run["plans"].values())
    assert "seasonal" in run["forecast_model"]["version"]
    proof=client.post("/api/evidence",json={"run_id":run["run_id"]});assert proof.status_code==200,proof.text
    p=proof.json();verified=inspect(p["evidence"],p["digest"],ROOT);assert verified["verified"],verified
    repeated=client.post("/api/compare",json={"date":date}).json()
    assert repeated["run_id"]==run["run_id"]
    for policy in run["plans"]:assert repeated["plans"][policy]["metrics"]==run["plans"][policy]["metrics"]
    runs.append({"date":date,"policies":len(run["plans"]),"run_id":run["run_id"],"evidence_verified":True,"unavailable_source_warnings":len(verified["warnings"])})
print(json.dumps({"status":"passed","network":"external denied; loopback IPC allowed","bulk_files":"absent","model":"past-only seasonal fallback","runs":runs},indent=2))
'''
    completed=subprocess.run([sys.executable,"-c",probe],cwd=destination,capture_output=True,text=True,timeout=180)
    print(completed.stdout,end="")
    if completed.returncode:
        print(completed.stderr,file=sys.stderr,end="");raise SystemExit(completed.returncode)
    report=json.loads(completed.stdout)
    report["isolated_source_path"]=str(destination.relative_to(ROOT))
    (runtime/"offline-check.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Verified source-copy operation using installed dependencies; setup installation is a separate check.")

if __name__=="__main__":main()
