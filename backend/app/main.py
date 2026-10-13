from __future__ import annotations
import csv,json,hashlib
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict
from backend.app.domain.schemas import Scenario,OptimizeRequest,ReplayRequest,EvidenceRequest,AttestRequest
from backend.app.domain.solver import solve
from backend.app.services.data import ROOT,available_dates,sources,prepare_intervals,envelope,forecast_day
from backend.app.services.simulator import compare
from backend.app.services import storage
from backend.app.services.evidence import make_evidence,verify_evidence
from backend.app.services.chain import call_bridge

app=FastAPI(title="GridProof",version="1.0.0",description="Modeled dispatch and reproducible evidence. No real carbon credits.")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000","http://127.0.0.1:3000"],allow_methods=["GET","POST"],allow_headers=["Content-Type"])

@app.exception_handler(ValueError)
async def value_error(request,exc): return JSONResponse(status_code=422,content={"error":{"code":"INVALID_INPUT_OR_SOURCE","message":str(exc)},**envelope()})

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc): return JSONResponse(status_code=422,content={"error":{"code":"INVALID_REQUEST","message":str(exc)},**envelope()})

@app.get("/api/health")
def health(): return {"service":"GridProof","version":"1.0.0","fixture_status":"ready" if available_dates() else "unavailable","available_dates":available_dates(),**envelope()}

@app.get("/api/sources")
def source_endpoint(): return {**sources(),**envelope()}

@app.get("/api/scenarios")
def scenarios(): return {"scenarios":[Scenario().model_dump()],"available_dates":available_dates(),**envelope()}

@app.get("/api/forecast")
def forecast(from_:str=Query(default="2025-08-12T00:00:00Z",alias="from"),hours:int=Query(default=24,ge=1,le=24)):
    try: issue=datetime.strptime(from_,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError: raise ValueError("Forecast issue must be a whole-second UTC timestamp ending Z")
    if issue.hour or issue.minute or issue.second or issue.strftime("%Y-%m-%dT%H:%M:%SZ")!=from_:
        raise ValueError("This historical predictor supports midnight UTC issues only")
    date=from_[:10]; values,model=forecast_day(date); intervals,_=prepare_intervals(date,Scenario())
    # Decision view masks all future actuals; observed outcomes are in replay/compare only.
    slots=[{**x,"ci_actual_g_per_kwh":None,"neso_historical_forecast_g_per_kwh":None,"solar_outcome_kwh":None,"shortwave_radiation_w_per_m2":None,"actual_known_at_decision":False} for x in intervals[:hours*2]]
    return {"intervals":slots,"forecast_model":model,"uncertainty":None,**envelope(date)}

@app.post("/api/optimize")
def optimize(request:OptimizeRequest):
    intervals,model=prepare_intervals(request.date,request.scenario)
    plan=solve(request.scenario,intervals,request.policy,request.carbon_weight,request.solver_time_limit_seconds)
    return {"date":request.date,"scenario":request.scenario.model_dump(),"plan":plan,"forecast_model":model,**envelope(request.date)}

@app.post("/api/compare")
def comparison(request:OptimizeRequest): return compare(request)

@app.post("/api/replay")
def replay(request:ReplayRequest):
    dates=request.dates or [request.date]
    runs=[compare(OptimizeRequest(**{**request.model_dump(exclude={"dates","seed"}),"date":date})) for date in dates]
    summary={}
    for policy in ["immediate","cost_first","carbon_first","hybrid","oracle"]:
        metrics=[r["plans"][policy]["metrics"] for r in runs if r["plans"][policy]["metrics"]]
        summary[policy]={"days":len(metrics),"emissions_kgco2":sum(x["emissions_kgco2"] for x in metrics),"cost_gbp":sum(x["cost_gbp"] for x in metrics),"violations":sum(len(r["plans"][policy]["constraints"]["violations"]) for r in runs)}
    replay_id="replay-"+hashlib.sha256(json.dumps({"run_ids":[r["run_id"] for r in runs],"seed":42},separators=(",",":"),sort_keys=True).encode()).hexdigest()[:20]
    value={"replay_id":replay_id,"run_id":runs[0]["run_id"],"runs":runs,"summary":summary,"seed":42,"evidence_scope":"one UTC day per evidence; use individual run_id for multi-day replay",**envelope(dates[0])}
    storage.put(replay_id,"replay",value);return value

@app.get("/api/benchmark")
def benchmark():
    path=ROOT/"experiments/benchmark_summary.json"
    if not path.exists(): return {"status":"unavailable","message":"Run scripts/run_benchmark.py",**envelope()}
    return {**json.loads(path.read_text(encoding="utf-8")),**envelope()}

@app.post("/api/evidence")
def evidence(request:EvidenceRequest):
    run_id=request.run_id
    if run_id.startswith("replay-"):
        replay=storage.get(run_id,"replay")
        if len(replay["runs"])!=1: raise ValueError("Multi-day evidence requires an individual run_id; each evidence covers one UTC day")
        run_id=replay["run_id"]
    return make_evidence(run_id,request.policy)

class VerifyRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence:dict
    expected_digest:str

@app.post("/api/verify")
def verify(request:VerifyRequest): return verify_evidence(request.evidence,request.expected_digest)

@app.post("/api/attest")
def attest(request:AttestRequest):
    proof=storage.get(request.evidence_id,"evidence")
    valid=verify_evidence(proof["evidence"],proof["digest"])
    if not valid["verified"]: raise ValueError("Prepared evidence no longer verifies")
    result=call_bridge({"action":"attest","network":request.network,"expected_chain_id":request.expected_chain_id,"digest":proof["digest"],"claim_scope":proof["evidence"]["claim_scope"]})
    if result.get("claim_key"): storage.put("chain-"+result["claim_key"],"chain",{"evidence_id":request.evidence_id,"receipt":result})
    return result

@app.get("/api/verify/{claim_key}")
def verify_chain(claim_key:str,digest:str|None=None,transaction_hash:str|None=None,expected_chain_id:int=31337):
    if digest is None:
        try:
            saved=storage.get("chain-"+claim_key,"chain");proof=storage.get(saved["evidence_id"],"evidence");digest=proof["digest"];transaction_hash=transaction_hash or saved["receipt"].get("transaction_hash")
        except ValueError: pass
    return call_bridge({"action":"verify","network":"local","expected_chain_id":expected_chain_id,"claim_key":claim_key,"digest":digest,"transaction_hash":transaction_hash})
