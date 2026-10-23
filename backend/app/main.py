from __future__ import annotations
import csv,json,hashlib,os,copy,asyncio,threading
from contextlib import asynccontextmanager
from typing import Literal
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
from backend.app.services.evidence import make_evidence,verify_evidence,digest
from backend.app.services.chain import call_bridge
from backend.app.services.readiness import ReadinessRequest,UpdateRequest,DepartureRequest,create_readiness,update_readiness,departure_assessment
from backend.app.fleet import service as carpark
from backend.app.fleet import evidence as carpark_evidence

@asynccontextmanager
async def lifespan(app):
    # Build the frozen departure model and quantile table once, off the request path.
    def warm():
        try:
            if carpark.available():carpark.selection();carpark.default_day();carpark.promises(carpark.day_sessions(carpark.default_day()))
        except Exception:pass
    threading.Thread(target=warm,daemon=True).start()
    yield

app=FastAPI(title="GridProof",version="1.0.0",description="Modeled dispatch and reproducible evidence. No real carbon credits.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.environ.get("GRIDPROOF_CORS_ORIGINS","http://localhost:3000,http://127.0.0.1:3000").split(","),allow_methods=["GET","POST"],allow_headers=["Content-Type"])
COMPUTE_SLOTS=asyncio.Semaphore(2)

@app.middleware("http")
async def bounded_compute(request,call_next):
    if int(request.headers.get("content-length","0"))>12_000_000:
        return JSONResponse(status_code=413,content={"error":{"code":"REQUEST_TOO_LARGE","message":"Evidence requests are limited to 12 MB"}})
    if os.environ.get("GRIDPROOF_READ_ONLY")=="1" and request.url.path in ("/api/compare","/api/optimize","/api/replay","/api/service/plan","/api/service/update","/api/carpark/day"):
        if COMPUTE_SLOTS.locked():
            return JSONResponse(status_code=429,content={"error":{"code":"COMPUTE_BUSY","message":"Two dispatch requests are already running; retry shortly"}})
        await COMPUTE_SLOTS.acquire()
        try:return await call_next(request)
        finally:COMPUTE_SLOTS.release()
    return await call_next(request)

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

@app.get("/api/demo")
def demo():
    path=ROOT/"data/sample/demo.json"
    if not path.exists(): raise ValueError("Run scripts/make_demo_fixture.py to prepare the cached demo")
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/api/demo-proof")
def recorded_proof():
    path=ROOT/"data/sample/evidence.json"
    if not path.exists():raise ValueError("Recorded release evidence is unavailable")
    return json.loads(path.read_text(encoding="utf-8"))

@app.get("/api/demo-attestation")
def recorded_attestation():
    proof=recorded_proof()
    if os.environ.get("GRIDPROOF_CHAIN_NETWORK","local")=="testnet":return public_proof()
    result=call_bridge({"action":"lookup","network":"local","expected_chain_id":31337,"claim_scope":proof["evidence"]["claim_scope"]})
    if result.get("status")=="VERIFIED" and result.get("digest","").lower()!=proof["digest"].lower():
        return {"ok":False,"status":"REPORT_DIGEST_MISMATCH","existing_claim":result,"message":"The current scope commits another report; the recorded release digest is not attested"}
    return result

@app.get("/api/chain-config")
def chain_config():
    network=os.environ.get("GRIDPROOF_CHAIN_NETWORK","local")
    if network not in ("local","testnet"): raise ValueError("Unsupported configured chain network")
    bridge=call_bridge({"action":"config","network":network})
    return {"network":network,"expected_chain_id":11155111 if network=="testnet" else 31337,"writes_enabled":network=="local" and os.environ.get("GRIDPROOF_ALLOW_CHAIN_WRITES","1")=="1" and os.environ.get("GRIDPROOF_READ_ONLY")!="1" and bridge.get("status")=="CONFIGURATION","explorer_url":"https://sepolia.etherscan.io" if network=="testnet" else None,"public_proof_configured":bridge.get("fixed_proof_configured",False),"deployment_configured":bridge.get("deployment_configured",False),"registry_address":bridge.get("registry_address"),"bridge_status":bridge.get("status")}

@app.get("/api/public-proof")
def public_proof():
    return call_bridge({"action":"fixed-proof","network":"testnet","expected_chain_id":11155111})

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

@app.post("/api/service/plan")
def service_plan(request:ReadinessRequest): return create_readiness(request)

@app.post("/api/service/update")
def service_update(request:UpdateRequest): return update_readiness(request)

@app.post("/api/service/departure")
def service_departure(request:DepartureRequest): return departure_assessment(request)

@app.post("/api/replay")
def replay(request:ReplayRequest):
    dates=request.dates or [request.date]
    runs=[compare(OptimizeRequest(**{**request.model_dump(exclude={"dates","seed"}),"date":date})) for date in dates]
    summary={}
    for policy in ["immediate","cost_first","carbon_first","hybrid","oracle","peak_aware","peak_first"]:
        metrics=[r["plans"][policy]["metrics"] for r in runs if r["plans"][policy]["metrics"]]
        summary[policy]={"days":len(metrics),"emissions_kgco2":sum(x["emissions_kgco2"] for x in metrics),"cost_gbp":sum(x["cost_gbp"] for x in metrics),"violations":sum(len(r["plans"][policy]["constraints"]["violations"]) for r in runs)}
    replay_id="replay-"+hashlib.sha256(json.dumps({"run_ids":[r["run_id"] for r in runs],"seed":42},separators=(",",":"),sort_keys=True).encode()).hexdigest()[:20]
    value={"replay_id":replay_id,"run_id":runs[0]["run_id"],"runs":runs,"summary":summary,"seed":42,"evidence_scope":"one UTC day per evidence; use individual run_id for multi-day replay",**envelope(dates[0])}
    storage.put(replay_id,"replay",value);return value

@app.get("/api/benchmark")
def benchmark():
    path=ROOT/"experiments/competition_v2/summary.json"
    if not path.exists(): path=ROOT/"experiments/benchmark_summary.json"
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

@app.get("/api/evidence/{evidence_id}")
def cached_evidence(evidence_id:str):
    if not evidence_id.startswith("evidence-") or len(evidence_id)>64: raise ValueError("Invalid evidence identifier")
    return prepared_proof(evidence_id)

def prepared_proof(evidence_id):
    try:return storage.get(evidence_id,"evidence")
    except ValueError:
        fixed=recorded_proof()
        if fixed["evidence_id"]==evidence_id:return fixed
        raise ValueError("Unknown or unavailable evidence identifier")

class VerifyRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence:dict
    expected_digest:str

@app.post("/api/verify")
def verify(request:VerifyRequest): return verify_evidence(request.evidence,request.expected_digest)

class AttackRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence_id:str

@app.post("/api/attack-demo")
def attack_demo(request:AttackRequest):
    proof=prepared_proof(request.evidence_id)
    forged=copy.deepcopy(proof["evidence"])
    for key in ("intervals","dispatch","baseline_dispatch"):
        for row in forged["inputs"][key]: row["ci_actual_g_per_kwh"]="0.000000000"
    for key in ("baseline_kgco2","plan_kgco2","difference_kgco2"): forged["results"][key]="0.000000000"
    forged["input_sha256"]=digest(forged["inputs"])
    fresh="0x"+digest(forged)
    return {"attack":"actual CI rewritten to zero, arithmetic updated, fresh SHA256; original upstream snapshots unchanged","new_digest":fresh,"rehashed_verification":verify_evidence(forged,fresh),"original_commit_verification":verify_evidence(forged,proof["digest"]),"published":False}

@app.post("/api/attest")
def attest(request:AttestRequest):
    if request.network!="local" or os.environ.get("GRIDPROOF_CHAIN_NETWORK","local")!="local" or os.environ.get("GRIDPROOF_READ_ONLY")=="1" or os.environ.get("GRIDPROOF_ALLOW_CHAIN_WRITES","1")!="1":
        raise HTTPException(status_code=403,detail="Chain writes are disabled. Public reviewers use read-only verification.")
    proof=prepared_proof(request.evidence_id)
    valid=verify_evidence(proof["evidence"],proof["digest"])
    if not valid["verified"]: raise ValueError("Prepared evidence no longer verifies")
    result=call_bridge({"action":"attest","network":request.network,"expected_chain_id":request.expected_chain_id,"digest":proof["digest"],"claim_scope":proof["evidence"]["claim_scope"]})
    if result.get("ok") and result.get("status")=="ATTESTED" and result.get("claim_key"):
        storage.put("chain-"+result["claim_key"],"chain",{"evidence_id":request.evidence_id,"receipt":result})
    return result

@app.get("/api/verify/{claim_key}")
def verify_chain(claim_key:str,digest:str|None=None,transaction_hash:str|None=None,expected_chain_id:int|None=None,network:Literal["local","testnet"]="local"):
    if digest is None:
        try:
            saved=storage.get("chain-"+claim_key,"chain");proof=storage.get(saved["evidence_id"],"evidence");digest=proof["digest"];transaction_hash=transaction_hash or saved["receipt"].get("transaction_hash")
        except ValueError: pass
    return call_bridge({"action":"verify","network":network,"expected_chain_id":expected_chain_id if expected_chain_id is not None else 11155111 if network=="testnet" else 31337,"claim_key":claim_key,"digest":digest,"transaction_hash":transaction_hash})

@app.get("/api/registry/{claim_key}")
def lookup_chain(claim_key:str,network:Literal["local","testnet"]="local",expected_chain_id:int|None=None,transaction_hash:str|None=None):
    return call_bridge({"action":"lookup","network":network,"expected_chain_id":expected_chain_id if expected_chain_id is not None else 11155111 if network=="testnet" else 31337,"claim_key":claim_key,"transaction_hash":transaction_hash})


class CarparkEvidenceRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    run_id:str

class CarparkForgeRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence_id:str
    attack:Literal["hide_shortfall","move_departure","drop_sessions"]

class CarparkAttestRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    evidence_id:str

@app.get("/api/carpark/config")
def carpark_config():
    if not carpark.available():
        return {"available":False,"message":"Real workplace session data is not downloaded. Run scripts/fetch_workplace_sessions.py (public, no account).","source":carpark.SOURCE}
    selection=carpark.selection()
    return {"available":True,"days":carpark.replay_days(),"day_sessions":carpark.day_counts(),"default_day":carpark.default_day(),"default_connection_kw":120,
            "modes":carpark.MODES,"selection":{"service_policy":selection["service_policy"],"carbon_flex":selection["carbon_flex"]},
            "source":carpark.SOURCE,"model":carpark.frozen()[3] | {"fingerprint":carpark.model_fingerprint()}}

@app.post("/api/carpark/day")
def carpark_day(request:carpark.DayRequest): return carpark.run_day(request)

@app.get("/api/carpark/results")
def carpark_results():
    path=ROOT/"experiments/carpark/test_results.json"
    if not path.exists():return {"status":"unavailable","message":"Run scripts/evaluate_carpark.py --stage test"}
    import pandas as pd
    summary=pd.read_csv(ROOT/"experiments/carpark/test_summary.csv")
    daily=pd.read_csv(ROOT/"experiments/carpark/test_daily.csv").groupby(["policy_name","cap"])[["emissions_kgco2","delivered_kwh"]].sum()
    intensity=(1000*daily.emissions_kgco2/daily.delivered_kwh).rename("g_per_delivered_kwh").reset_index()
    summary=summary.merge(intensity,on=["policy_name","cap"],how="left")
    result=json.loads(path.read_text(encoding="utf-8"))
    followup=None
    fpath=ROOT/"experiments/carpark_followup/test_results.json"
    if fpath.exists():
        fres=json.loads(fpath.read_text(encoding="utf-8"))
        fsum=pd.read_csv(ROOT/"experiments/carpark_followup/test_summary.csv")
        fsum=fsum.astype(object).where(pd.notna(fsum),None)
        followup={"status":"exploratory_post_review","days":fres["days"],"sessions":fres["sessions"],"impossible_requests":fres["infeasible_requests_decision_time"],
                  "capacity_needed_kw":fres["capacity_needed_kw"],"paired":fres["paired"],"selection":fres["selection"],"summary":fsum.to_dict("records")}
    return {"status":"ready","followup":followup,"days":result["days"],"sessions":result["sessions"],"capacity_needed_kw":result["capacity_needed_kw"],
            "paired":result["paired"],"coverage":result["departure_coverage_test"],"selection":result["selection"]["service_policy"],
            "carbon_flex":result["selection"]["carbon_flex"],"summary":summary.to_dict("records")}

@app.post("/api/carpark/evidence")
def carpark_build_evidence(request:CarparkEvidenceRequest): return carpark_evidence.build(request.run_id)

@app.post("/api/carpark/verify")
def carpark_verify(request:VerifyRequest): return carpark_evidence.verify(request.evidence,request.expected_digest)

@app.post("/api/carpark/forge")
def carpark_forge(request:CarparkForgeRequest): return carpark_evidence.forge(request.evidence_id,request.attack)

@app.post("/api/carpark/attest")
def carpark_attest(request:CarparkAttestRequest):
    if os.environ.get("GRIDPROOF_CHAIN_NETWORK","local")!="local" or os.environ.get("GRIDPROOF_READ_ONLY")=="1" or os.environ.get("GRIDPROOF_ALLOW_CHAIN_WRITES","1")!="1":
        raise HTTPException(status_code=403,detail="Chain writes are disabled. Reviewers use read-only verification.")
    proof=storage.get(request.evidence_id,"carpark-evidence")
    if not carpark_evidence.verify(proof["evidence"],proof["digest"])["verified"]:raise ValueError("Only a fully verified record can be registered")
    scope=proof["evidence"]["claim_scope"]
    result=call_bridge({"action":"attest","network":"local","expected_chain_id":31337,"digest":proof["digest"],"claim_scope":scope})
    if result.get("status")=="ATTESTED" and result.get("claim_key"):
        result["readback"]=call_bridge({"action":"verify","network":"local","expected_chain_id":31337,"claim_key":result["claim_key"],"digest":proof["digest"],"transaction_hash":result.get("transaction_hash")})
    return result
