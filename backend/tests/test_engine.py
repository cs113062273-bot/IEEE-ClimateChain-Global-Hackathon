from __future__ import annotations
import copy,json,subprocess,sys
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.domain.schemas import Scenario,OptimizeRequest
from backend.app.domain.solver import solve,validate_inputs
from backend.app.ml.forecast import features
from backend.app.services.data import prepare_intervals,ci_frame,ROOT
from backend.app.services.simulator import compare
from backend.app.services.evidence import canonical_bytes,digest,make_evidence,verify_evidence
from backend.app.main import app

@pytest.fixture
def intervals():return prepare_intervals("2025-08-12",Scenario())[0]

@pytest.mark.parametrize("policy",["immediate","cost-first","carbon-first","hybrid","oracle"])
def test_physical_constraints_and_fair_workloads(intervals,policy):
    scenario=Scenario();plan=solve(scenario,intervals,policy)
    assert plan["constraints"]["verified"],plan["constraints"]
    assert plan["metrics"]["workload_kwh"]==62
    assert all(j["completed"] for j in plan["constraints"]["ev_jobs"])
    assert abs(plan["constraints"]["terminal_soc_delta_kwh"])<2e-5
    assert all(min(x["battery_charge_kwh"],x["battery_discharge_kwh"])<2e-5 for x in plan["dispatch"])

def test_infeasible_ev_not_optimized(intervals):
    scenario=Scenario(ev_jobs=[{"id":"impossible","energy_kwh":100,"arrival_slot":30,"deadline_slot":31,"max_kw":1}])
    plan=solve(scenario,intervals,"carbon-first")
    assert plan["solver"]["status"]=="infeasible" and not plan["solver"]["success"]

@pytest.mark.parametrize("mutation",["missing","duplicate","reverse","null","negative","tz","source"])
def test_data_rejection(intervals,mutation):
    records=copy.deepcopy(intervals)
    if mutation=="missing":records.pop(7)
    elif mutation=="duplicate":records[8]=records[7]
    elif mutation=="reverse":records.reverse()
    elif mutation=="null":records[7]["ci_actual_g_per_kwh"]=None
    elif mutation=="negative":records[7]["tariff_gbp_per_kwh"]=-1
    elif mutation=="tz":records[7]["start_utc"]=records[7]["start_utc"].replace("Z","+01:00")
    elif mutation=="source":records[7]["source_refs"]=[]
    with pytest.raises(ValueError):validate_inputs(records)

def test_no_future_feature_leakage():
    frame=ci_frame();issue=frame.index[2000].normalize();past=frame.loc[frame.index<issue]
    before=features(past,issue);modified=frame.copy();modified.loc[modified.index>=issue,"grid_ci_actual_g_per_kwh"]=999
    after=features(modified.loc[modified.index<issue],issue)
    np.testing.assert_array_equal(before,after)
    with pytest.raises(ValueError):features(frame,issue)

def test_future_weather_only_changes_replay_not_decisions(intervals):
    original=solve(Scenario(),intervals,"carbon-first");changed=copy.deepcopy(intervals)
    for x in changed:x["solar_outcome_kwh"]*=.2;x["ci_actual_g_per_kwh"]*=1.3
    replayed=solve(Scenario(),changed,"carbon-first")
    for a,b in zip(original["dispatch"],replayed["dispatch"]):
        for key in ["ev_charge_kwh","batch_load_kwh","battery_charge_kwh","battery_discharge_kwh","grid_import_forecast_kwh"]:assert abs(a[key]-b[key])<1e-5

def test_pv_curtail_no_negative_import(intervals):
    changed=copy.deepcopy(intervals)
    for x in changed:x["pv_available_kwh"]=100;x["solar_outcome_kwh"]=100
    plan=solve(Scenario(),changed,"carbon-first")
    assert plan["constraints"]["verified"]
    assert all(x["grid_import_kwh"]>=0 for x in plan["dispatch"])
    assert sum(x["pv_curtail_kwh"] for x in plan["dispatch"])>0

def test_shared_charger_and_batches(intervals):
    scenario=Scenario(charger_station_kw=11,batch_jobs=[{"id":"one","energy_kwh":8,"duration_slots":4,"earliest_start_slot":12,"latest_end_slot":24},{"id":"two","energy_kwh":8,"duration_slots":4,"earliest_start_slot":12,"latest_end_slot":24}])
    plan=solve(scenario,intervals,"hybrid");assert plan["constraints"]["verified"]
    assert all(x["ev_charge_kwh"]<=5.5+2e-5 for x in plan["dispatch"])
    assert abs(plan["batch_starts"]["one"]-plan["batch_starts"]["two"])>=4

def test_carbon_units_and_zero_battery(intervals):
    plan=solve(Scenario(battery_capacity_kwh=0),intervals,"immediate")
    expected=sum(x["grid_import_kwh"]*x["ci_actual_g_per_kwh"]/1000 for x in plan["dispatch"])
    assert plan["metrics"]["emissions_kgco2"]==pytest.approx(expected)
    assert all(x["soc_end_kwh"]==0 for x in plan["dispatch"])

def test_canonical_encoding_and_tamper():
    a={"z":-0.0,"a":[1.23456789055,True,None,"London"]};b={"a":a["a"],"z":a["z"]}
    assert canonical_bytes(a)==canonical_bytes(b)
    assert b'"0.000000000"' in canonical_bytes(a)
    with pytest.raises(ValueError):canonical_bytes({"x":float("nan")})

def test_evidence_independent_metrics_and_tamper(tmp_path):
    run=compare(OptimizeRequest());proof=make_evidence(run["run_id"])
    assert verify_evidence(proof["evidence"],proof["digest"])["verified"]
    copied=copy.deepcopy(proof["evidence"]);copied["results"]["plan_kgco2"]="123.000000000"
    assert not verify_evidence(copied,proof["digest"])["verified"]
    assert not verify_evidence(copied,"0x"+digest(copied))["verified"]
    path=tmp_path/"evidence.json";path.write_text(json.dumps(proof),encoding="utf-8")
    result=subprocess.run([sys.executable,str(ROOT/"scripts/verify_evidence.py"),str(path)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr

def test_api_forecast_and_infeasible_state():
    client=TestClient(app)
    assert client.get("/api/health").json()["fixture_status"]=="ready"
    forecast=client.get("/api/forecast").json()
    assert all(x["ci_actual_g_per_kwh"] is None for x in forecast["intervals"])
    assert all(x["solar_outcome_kwh"] is None and x["shortwave_radiation_w_per_m2"] is None for x in forecast["intervals"])
    response=client.post("/api/compare",json={"scenario":{"ev_jobs":[{"id":"bad","energy_kwh":100,"arrival_slot":30,"deadline_slot":31,"max_kw":1}]}})
    assert response.status_code==422 and response.json()["error"]["code"]=="INVALID_INPUT_OR_SOURCE"
    assert client.post("/api/optimize",json={"scenario":{"eta_charge":0}}).status_code==422

def test_solver_failure_safe_fallback(intervals,monkeypatch):
    import backend.app.domain.solver as module
    def fail(*args,**kwargs):raise RuntimeError("test solver outage")
    monkeypatch.setattr(module,"milp",fail)
    plan=solve(Scenario(),intervals,"hybrid")
    assert plan["solver"]["status"]=="fallback_immediate" and plan["constraints"]["verified"]

def test_chain_unavailable_honest(monkeypatch):
    import backend.app.services.chain as chain
    def fail(*args,**kwargs):raise OSError("unreachable")
    monkeypatch.setattr(chain.subprocess,"run",fail)
    result=chain.call_bridge({"action":"verify"})
    assert result["status"]=="UNVERIFIABLE" and not result["ok"]

@pytest.mark.parametrize("field,value",[("pv_curtail_kwh",-1),("export_kwh",1),("ev_charge_kwh",-1),("soc_start_kwh",999)])
def test_rehashed_invalid_energy_rejected(field,value):
    run=compare(OptimizeRequest());proof=make_evidence(run["run_id"]);evidence=copy.deepcopy(proof["evidence"])
    evidence["inputs"]["dispatch"][0][field]=str(value)
    evidence["input_sha256"]=digest(evidence["inputs"])
    assert not verify_evidence(evidence,"0x"+digest(evidence))["verified"]

def test_time_limit_safe_fallback(intervals,monkeypatch):
    import backend.app.domain.solver as module
    from types import SimpleNamespace
    monkeypatch.setattr(module,"milp",lambda *a,**k:SimpleNamespace(x=None,status=1,message="time limit without incumbent"))
    result=solve(Scenario(),intervals,"carbon-first")
    assert result["solver"]["status"]=="fallback_immediate" and result["constraints"]["verified"]

@pytest.mark.parametrize("value",["NaN","Infinity","-Infinity"])
def test_nonfinite_claim_rejected_by_both_verifiers(value):
    from scripts.verify_evidence import inspect
    run=compare(OptimizeRequest());proof=make_evidence(run["run_id"]);evidence=copy.deepcopy(proof["evidence"])
    evidence["results"]["plan_kgco2"]=value;expected="0x"+digest(evidence)
    assert not verify_evidence(evidence,expected)["verified"]
    assert not inspect(evidence,expected,ROOT)["verified"]

def test_canonical_overflow_meaningful_error():
    with pytest.raises(ValueError,match="magnitude"):canonical_bytes({"x":1e30})
    client=TestClient(app)
    response=client.post("/api/verify",json={"evidence":{"x":1e30},"expected_digest":"0x"+"0"*64})
    assert response.status_code==422

@pytest.mark.parametrize("issue",["2025-08-12T12:00:00Z","2025-08-12T00:00:00+08:00","2025-08-12junk","2025-08-12T00:00:30Z"])
def test_forecast_rejects_non_midnight_or_malformed(issue):
    assert TestClient(app).get("/api/forecast",params={"from":issue,"hours":6}).status_code==422

def test_selection_timing_prevents_validation_lookahead():
    from backend.app.ml.forecast import predict_day
    import pandas as pd
    frame=ci_frame();issue=pd.Timestamp("2025-08-12",tz="UTC")
    values,method=predict_day(frame.loc[frame.index<issue],issue)
    assert method=="past-only-seven-day-seasonal-median-v1"

def test_replay_ids_and_evidence_scope():
    client=TestClient(app)
    single=client.post("/api/replay",json={"dates":["2025-01-15"]}).json()
    multi=client.post("/api/replay",json={"dates":["2025-01-15","2025-08-12"]}).json()
    assert single["replay_id"]!=multi["replay_id"]
    assert client.post("/api/evidence",json={"run_id":multi["replay_id"]}).status_code==422
    assert client.post("/api/evidence",json={"run_id":single["replay_id"]}).status_code==200

def test_rehashed_unsupported_claim_category_rejected():
    from scripts.verify_evidence import inspect
    proof=make_evidence(compare(OptimizeRequest())["run_id"]);evidence=copy.deepcopy(proof["evidence"])
    evidence["claim_scope"]["category"]="certified-carbon-removal"
    expected="0x"+digest(evidence)
    assert not verify_evidence(evidence,expected)["verified"] and not inspect(evidence,expected,ROOT)["verified"]

def test_concurrent_requests_serialize_native_solver():
    from concurrent.futures import ThreadPoolExecutor
    def request(_):
        with TestClient(app) as client:
            response=client.post("/api/optimize",json={"date":"2025-01-15","policy":"hybrid"})
            assert response.status_code==200,response.text
            return response.json()["plan"]["constraints"]["verified"]
    with ThreadPoolExecutor(max_workers=3) as pool:assert all(pool.map(request,range(3)))

def test_compare_replay_same_scenario_weight_identity_and_metrics():
    with TestClient(app) as client:
        body={"date":"2025-08-12","scenario":{"battery_capacity_kwh":60},"carbon_weight":.2,"policy":"cost-first"}
        compared=client.post("/api/compare",json=body)
        assert compared.status_code==200,compared.text
        expected=compared.json()
        # Replay receives the UI's full validated scenario; compare used defaults
        # for other fields. Both represent precisely the same typed request.
        replay_body={**body,"scenario":expected["scenario"],"solver_time_limit_seconds":10.0}
        replay=client.post("/api/replay",json=replay_body)
        assert replay.status_code==200,replay.text
        actual=replay.json()["runs"][0]
        assert actual["run_id"]==expected["run_id"]
        assert actual["scenario"]==expected["scenario"]
        for policy in expected["plans"]:
            assert actual["plans"][policy]["metrics"]==expected["plans"][policy]["metrics"]
