"""HiGHS MILP with independently reconstructed numerical constraints."""
from __future__ import annotations
import time,warnings
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import scipy
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
from .schemas import Scenario

T=48
DT=.5
TOL=2e-5
# Native HiGHS lifetime belongs to one persistent worker. FastAPI request worker
# threads are transient; creating native scheduler state on each caused a
# reproducible Windows access violation in repeated replay API requests.
SOLVER_WORKER=ThreadPoolExecutor(max_workers=1,thread_name_prefix="gridproof-highs")

def _run_milp(*args,**kwargs):
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore",message="Unrecognized options detected")
        return milp(*args,**kwargs)

def validate_inputs(intervals):
    from datetime import datetime, timedelta
    if len(intervals)!=T:
        raise ValueError("Exactly 48 complete consecutive UTC half-hour intervals required")
    previous=None
    for x in intervals:
        start=datetime.fromisoformat(x["start_utc"].replace("Z","+00:00"))
        end=datetime.fromisoformat(x["end_utc"].replace("Z","+00:00"))
        if start.utcoffset()!=timedelta(0) or end.utcoffset()!=timedelta(0) or end-start!=timedelta(minutes=30):
            raise ValueError("Intervals must be UTC and exactly 30 minutes")
        if previous is not None and start!=previous:
            raise ValueError("Missing, duplicate, or out-of-order half-hour timestamp")
        previous=end
        for key,maximum in [("ci_forecast_g_per_kwh",1500),("ci_actual_g_per_kwh",1500),("fixed_load_kwh",200),("pv_available_kwh",200),("tariff_gbp_per_kwh",10)]:
            val=x.get(key)
            if val is None or not np.isfinite(val) or not 0<=val<=maximum:
                raise ValueError(f"Invalid or missing {key}")
        if not x.get("source_refs"):
            raise ValueError("Source provenance required")

def _immediate_jobs(scenario):
    ev=np.zeros((len(scenario.ev_jobs),T)); batch=np.zeros(T); starts={}
    for j,job in enumerate(scenario.ev_jobs):
        remaining=job.energy_kwh
        for t in range(job.arrival_slot,job.deadline_slot):
            take=min(remaining,job.max_kw*DT,max(0,scenario.charger_station_kw*DT-ev[:,t].sum()))
            ev[j,t]=take; remaining-=take
        if remaining>TOL: raise ValueError(f"Immediate EV schedule cannot complete {job.id} under shared charger cap")
    occupancy=np.zeros(T)
    for job in scenario.batch_jobs:
        candidates=range(job.earliest_start_slot,job.latest_end_slot-job.duration_slots+1)
        start=next((s for s in candidates if np.all(occupancy[s:s+job.duration_slots]<scenario.max_batch_concurrency)),None)
        if start is None: raise ValueError(f"Immediate batch cannot complete {job.id}")
        starts[job.id]=start; occupancy[start:start+job.duration_slots]+=1
        batch[start:start+job.duration_slots]+=job.energy_kwh/job.duration_slots
    return ev,batch,starts

def solve(scenario:Scenario,intervals:list[dict],policy="hybrid",carbon_weight=.7,time_limit=10):
    validate_inputs(intervals)
    started=time.perf_counter()
    if policy=="peak-first":
        # No carbon, tariff or solar forecast enters this policy's decisions.
        # Shared observed outcome PV is still applied after fixed decisions.
        intervals=[{**x,"pv_available_kwh":0.0,"pv_forecast_kwh":0.0} for x in intervals]
    fixed=np.array([x["fixed_load_kwh"] for x in intervals]); pv=np.array([x["pv_available_kwh"] for x in intervals])
    ci=np.array([x["ci_forecast_g_per_kwh"] for x in intervals]); price=np.array([x["tariff_gbp_per_kwh"] for x in intervals])
    if policy=="oracle": ci=np.array([x["ci_actual_g_per_kwh"] for x in intervals])
    if policy=="immediate":
        try:
            ev,batch,starts=_immediate_jobs(scenario)
            load=fixed+ev.sum(axis=0)+batch; used=np.minimum(pv,load); grid=load-used
            if np.max(grid)>scenario.max_grid_import_kw*DT+TOL: raise ValueError("Immediate dispatch exceeds grid import cap")
            if scenario.peak_cap_kw is not None:
                envelope=load if scenario.peak_risk_mode=="zero-pv-guard" else grid
                if np.max(envelope)>scenario.peak_cap_kw*DT+TOL: raise ValueError("Immediate dispatch exceeds configured peak cap/envelope")
            dispatch=_dispatch(intervals,grid,np.zeros(T),np.zeros(T),np.full(T+1,scenario.battery_capacity_kwh*scenario.soc_initial_fraction),ev,batch,used,pv-used)
            return _result(scenario,dispatch,starts,policy,started,"feasible_baseline",None,"Earliest workloads; battery idle; PV self-consumption and curtailment")
        except ValueError as e: return _failure(policy,str(e),started,"infeasible")
    # Variable blocks: import, charge, discharge, PV-used, SoC(49), charge mode, EV(job,48), batch starts.
    offset=0; idx={}
    for name,n in [("grid",T),("charge",T),("discharge",T),("pv",T),("soc",T+1),("mode",T),("ev",len(scenario.ev_jobs)*T)]:
        idx[name]=np.arange(offset,offset+n); offset+=n
    batch_indices={}
    for job in scenario.batch_jobs:
        starts=list(range(job.earliest_start_slot,job.latest_end_slot-job.duration_slots+1))
        batch_indices[job.id]={s:offset+i for i,s in enumerate(starts)}; offset+=len(starts)
    peak_enabled=scenario.peak_weight>0 or scenario.peak_cap_kw is not None or policy=="peak-first"
    if peak_enabled: idx["peak"]=np.array([offset]);offset+=1
    n=offset; lower=np.zeros(n); upper=np.full(n,np.inf); integer=np.zeros(n)
    upper[idx["grid"]]=scenario.max_grid_import_kw*DT
    upper[idx["charge"]]=scenario.charge_kw*DT if scenario.battery_capacity_kwh else 0
    upper[idx["discharge"]]=scenario.discharge_kw*DT if scenario.battery_capacity_kwh else 0
    upper[idx["pv"]]=pv
    lower[idx["soc"]]=scenario.battery_capacity_kwh*scenario.soc_min_fraction
    upper[idx["soc"]]=scenario.battery_capacity_kwh*scenario.soc_max_fraction
    initial=scenario.battery_capacity_kwh*scenario.soc_initial_fraction
    lower[idx["soc"][[0,-1]]]=initial; upper[idx["soc"][[0,-1]]]=initial
    upper[idx["mode"]]=1; integer[idx["mode"]]=1
    for j,job in enumerate(scenario.ev_jobs):
        ev_idx=idx["ev"][j*T:(j+1)*T]; upper[ev_idx]=0
        upper[ev_idx[job.arrival_slot:job.deadline_slot]]=job.max_kw*DT
        if job.energy_kwh>(job.deadline_slot-job.arrival_slot)*job.max_kw*DT+TOL:
            return _failure(policy,f"EV {job.id}: energy exceeds arrival/deadline charging capacity",started,"infeasible")
    for starts in batch_indices.values():
        for i in starts.values(): upper[i]=1; integer[i]=1
    if peak_enabled: upper[idx["peak"]]=scenario.peak_cap_kw if scenario.peak_cap_kw is not None else np.inf
    rows=[]; lo=[]; hi=[]
    def row(coeff,a,b): rows.append(coeff); lo.append(a); hi.append(b)
    for t in range(T):
        coeff={int(idx["grid"][t]):1,int(idx["discharge"][t]):1,int(idx["pv"][t]):1,int(idx["charge"][t]):-1}
        for j in range(len(scenario.ev_jobs)): coeff[int(idx["ev"][j*T+t])]=-1
        occ={}
        for job in scenario.batch_jobs:
            for start,i in batch_indices[job.id].items():
                if start<=t<start+job.duration_slots: coeff[i]=-job.energy_kwh/job.duration_slots; occ[i]=1
        row(coeff,fixed[t],fixed[t])
        row({int(idx["soc"][t+1]):1,int(idx["soc"][t]):-1,int(idx["charge"][t]):-scenario.eta_charge,int(idx["discharge"][t]):1/scenario.eta_discharge},0,0)
        row({int(idx["charge"][t]):1,int(idx["mode"][t]):-scenario.charge_kw*DT},-np.inf,0)
        row({int(idx["discharge"][t]):1,int(idx["mode"][t]):scenario.discharge_kw*DT},-np.inf,scenario.discharge_kw*DT)
        row({int(idx["ev"][j*T+t]):1 for j in range(len(scenario.ev_jobs))},0,scenario.charger_station_kw*DT)
        if occ: row(occ,0,scenario.max_batch_concurrency)
        if peak_enabled:
            z=int(idx["peak"][0])
            if scenario.peak_risk_mode=="zero-pv-guard" or policy=="peak-first":
                # The envelope ignores all PV: import under any nonnegative
                # replay PV cannot exceed net demand. No future weather needed.
                peak_coeff={int(idx["charge"][t]):1,int(idx["discharge"][t]):-1,z:-DT}
                for j in range(len(scenario.ev_jobs)):peak_coeff[int(idx["ev"][j*T+t])]=1
                for job in scenario.batch_jobs:
                    for start,i in batch_indices[job.id].items():
                        if start<=t<start+job.duration_slots:peak_coeff[i]=job.energy_kwh/job.duration_slots
                row(peak_coeff,-np.inf,-fixed[t])
            else: row({int(idx["grid"][t]):1,z:-DT},-np.inf,0)
    for j,job in enumerate(scenario.ev_jobs): row({int(i):1 for i in idx["ev"][j*T:(j+1)*T]},job.energy_kwh,job.energy_kwh)
    for starts in batch_indices.values(): row({i:1 for i in starts.values()},1,1)
    matrix=lil_matrix((len(rows),n),dtype=float)
    for k,coeff in enumerate(rows):
        for i,value in coeff.items(): matrix[k,i]=value
    objective=np.zeros(n)
    # Disclosed fixed references across all policies: 50 kg and GBP100 per day.
    weight=1 if policy in ("carbon-first","oracle") else 0 if policy=="cost-first" else carbon_weight
    objective[idx["grid"]]=weight*ci/1000/50+(1-weight)*price/100
    if policy=="peak-first": objective[idx["grid"]]=0
    if peak_enabled: objective[idx["peak"]]=(1.0 if policy=="peak-first" else scenario.peak_weight)/scenario.peak_reference_kw
    # Physical battery losses already included. Small cycling tie-breaker (not a hidden cost model).
    objective[idx["charge"]]=1e-7; objective[idx["discharge"]]=1e-7
    try:
        result=SOLVER_WORKER.submit(_run_milp,objective,integrality=integer,bounds=Bounds(lower,upper),constraints=LinearConstraint(matrix.tocsc(),lo,hi),options={"time_limit":time_limit,"mip_rel_gap":1e-6,"presolve":True,"threads":1}).result()
    except Exception as e: return _fallback(scenario,intervals,policy,started,f"Solver error: {type(e).__name__}: {e}")
    if result.x is None:
        if result.status==2: return _failure(policy,result.message,started,"infeasible")
        return _fallback(scenario,intervals,policy,started,result.message)
    x=np.maximum(result.x,0); ev=x[idx["ev"]].reshape((len(scenario.ev_jobs),T)); batch=np.zeros(T); chosen={}
    for job in scenario.batch_jobs:
        start=max(batch_indices[job.id],key=lambda s:x[batch_indices[job.id][s]])
        chosen[job.id]=start; batch[start:start+job.duration_slots]+=job.energy_kwh/job.duration_slots
    dispatch=_dispatch(intervals,x[idx["grid"]],x[idx["charge"]],x[idx["discharge"]],x[idx["soc"]],ev,batch,x[idx["pv"]],pv-x[idx["pv"]])
    plan=_result(scenario,dispatch,chosen,policy,started,"optimal" if result.status==0 else "feasible_time_limit",float(result.mip_gap) if result.mip_gap is not None else None,result.message)
    plan["solver"]["objective_value"]=float(result.fun)
    if peak_enabled:
        plan["solver"]["peak_epigraph_kw"]=float(x[idx["peak"][0]])
        plan["solver"]["objective_references"].update({"peak_kw":scenario.peak_reference_kw,"peak_weight":1.0 if policy=="peak-first" else scenario.peak_weight,"peak_risk_mode":"zero-pv-guard" if policy=="peak-first" else scenario.peak_risk_mode})
    if not plan["constraints"]["verified"]: return _fallback(scenario,intervals,policy,started,"Solver candidate failed independent constraint verification")
    return plan

def _fallback(scenario,intervals,policy,started,reason):
    plan=solve(scenario,intervals,"immediate")
    if plan.get("dispatch"):
        plan["policy"]=policy; plan["solver"]["status"]="fallback_immediate"; plan["solver"]["message"]=reason; plan["solver"]["seconds"]=time.perf_counter()-started
        return plan
    return _failure(policy,reason+"; no feasible immediate fallback",started,"unavailable")

def _failure(policy,reason,started,status):
    return {"policy":policy,"solver":{"name":"HiGHS/scipy.milp","scipy_version":scipy.__version__,"status":status,"success":False,"seconds":time.perf_counter()-started,"message":reason,"constraints_verified":False},"constraints":{"verified":False,"violations":[reason]},"dispatch":[],"metrics":None,"batch_starts":{}}

def _dispatch(intervals,grid,charge,discharge,soc,ev,batch,used,curtail):
    records=[]
    for t,source in enumerate(intervals):
        record=dict(source)
        record.update({"grid_import_kwh":float(grid[t]),"battery_charge_kwh":float(charge[t]),"battery_discharge_kwh":float(discharge[t]),"soc_start_kwh":float(soc[t]),"soc_end_kwh":float(soc[t+1]),"ev_charge_kwh":float(ev[:,t].sum()),"ev_by_job_kwh":[float(v) for v in ev[:,t]],"batch_load_kwh":float(batch[t]),"pv_used_kwh":float(used[t]),"pv_curtail_kwh":float(max(0,curtail[t])),"export_kwh":0.0})
        records.append(record)
    return records

def check_constraints(scenario,dispatch,starts):
    violations=[]; residuals=[]
    try: validate_inputs(dispatch)
    except (ValueError,KeyError,TypeError) as exc:
        return {"verified":False,"violations":[str(exc)],"max_balance_residual_kwh":None,"terminal_soc_delta_kwh":None,"ev_jobs":[],"tolerance_kwh":TOL}
    for t,x in enumerate(dispatch):
        energy_fields=["grid_import_kwh","battery_charge_kwh","battery_discharge_kwh","soc_start_kwh","soc_end_kwh","ev_charge_kwh","batch_load_kwh","pv_used_kwh","pv_curtail_kwh","export_kwh"]
        if any(not np.isfinite(x[k]) or x[k]<-TOL for k in energy_fields): violations.append(f"Negative or nonfinite energy at {t}");continue
        if len(x["ev_by_job_kwh"])!=len(scenario.ev_jobs) or any(not np.isfinite(v) or v< -TOL for v in x["ev_by_job_kwh"]): violations.append(f"Invalid per-job EV energy at {t}");continue
        if abs(sum(x["ev_by_job_kwh"])-x["ev_charge_kwh"])>TOL: violations.append(f"EV aggregate mismatch at {t}")
        if x["export_kwh"]>TOL: violations.append(f"Export forbidden at {t}")
        if x["pv_used_kwh"]>x["pv_available_kwh"]+TOL: violations.append(f"PV used exceeds available at {t}")
        if not scenario.battery_capacity_kwh*scenario.soc_min_fraction-TOL<=x["soc_start_kwh"]<=scenario.battery_capacity_kwh*scenario.soc_max_fraction+TOL: violations.append(f"Initial slot SoC bounds at {t}")
        residual=x["grid_import_kwh"]+x["battery_discharge_kwh"]+x["pv_used_kwh"]-x["fixed_load_kwh"]-x["ev_charge_kwh"]-x["batch_load_kwh"]-x["battery_charge_kwh"]
        residuals.append(abs(residual))
        if abs(residual)>TOL: violations.append(f"Energy balance at {t}")
        expect=x["soc_start_kwh"]+scenario.eta_charge*x["battery_charge_kwh"]-x["battery_discharge_kwh"]/scenario.eta_discharge
        if abs(expect-x["soc_end_kwh"])>TOL: violations.append(f"SoC dynamics at {t}")
        if not scenario.battery_capacity_kwh*scenario.soc_min_fraction-TOL<=x["soc_end_kwh"]<=scenario.battery_capacity_kwh*scenario.soc_max_fraction+TOL: violations.append(f"SoC bounds at {t}")
        if min(x["battery_charge_kwh"],x["battery_discharge_kwh"])>TOL: violations.append(f"Simultaneous battery charge/discharge at {t}")
        if x["grid_import_kwh"]< -TOL or x["grid_import_kwh"]>scenario.max_grid_import_kw*DT+TOL: violations.append(f"Grid cap at {t}")
        if scenario.peak_cap_kw is not None:
            net=x["fixed_load_kwh"]+x["ev_charge_kwh"]+x["batch_load_kwh"]+x["battery_charge_kwh"]-x["battery_discharge_kwh"]
            if x["grid_import_kwh"]>scenario.peak_cap_kw*DT+TOL:violations.append(f"Replay peak cap at {t}")
            if scenario.peak_risk_mode=="zero-pv-guard" and net>scenario.peak_cap_kw*DT+TOL:violations.append(f"Zero-PV peak guard at {t}")
        if x["battery_charge_kwh"]>scenario.charge_kw*DT+TOL or x["battery_discharge_kwh"]>scenario.discharge_kw*DT+TOL: violations.append(f"Battery power at {t}")
        if abs(x["pv_used_kwh"]+x["pv_curtail_kwh"]-x["pv_available_kwh"])>TOL: violations.append(f"PV allocation at {t}")
        if x["ev_charge_kwh"]>scenario.charger_station_kw*DT+TOL: violations.append(f"Shared charger cap at {t}")
        if t and abs(dispatch[t-1]["soc_end_kwh"]-x["soc_start_kwh"])>TOL: violations.append(f"SoC continuity at {t}")
    initial=scenario.battery_capacity_kwh*scenario.soc_initial_fraction
    if abs(dispatch[0]["soc_start_kwh"]-initial)>TOL or abs(dispatch[-1]["soc_end_kwh"]-initial)>TOL: violations.append("Initial/terminal SoC")
    ev_results=[]
    for j,job in enumerate(scenario.ev_jobs):
        energy=sum(x["ev_by_job_kwh"][j] for x in dispatch if len(x["ev_by_job_kwh"])>j)
        if abs(energy-job.energy_kwh)>TOL: violations.append(f"EV energy {job.id}")
        for t,x in enumerate(dispatch):
            if len(x["ev_by_job_kwh"])<=j: continue
            if x["ev_by_job_kwh"][j]>job.max_kw*DT+TOL or (not job.arrival_slot<=t<job.deadline_slot and x["ev_by_job_kwh"][j]>TOL): violations.append(f"EV window/cap {job.id} at {t}")
        ev_results.append({"id":job.id,"required_kwh":job.energy_kwh,"delivered_kwh":energy,"completed":abs(energy-job.energy_kwh)<=TOL})
    expected=np.zeros(T); occupancy=np.zeros(T)
    for job in scenario.batch_jobs:
        start=starts.get(job.id,-100)
        if not job.earliest_start_slot<=start<=job.latest_end_slot-job.duration_slots: violations.append(f"Batch start {job.id}"); continue
        expected[start:start+job.duration_slots]+=job.energy_kwh/job.duration_slots; occupancy[start:start+job.duration_slots]+=1
    if np.max(np.abs(expected-np.array([x["batch_load_kwh"] for x in dispatch])))>TOL: violations.append("Batch contiguity/energy")
    if np.max(occupancy)>scenario.max_batch_concurrency: violations.append("Batch concurrency")
    return {"verified":not violations,"violations":violations,"max_balance_residual_kwh":max(residuals),"terminal_soc_delta_kwh":dispatch[-1]["soc_end_kwh"]-initial,"ev_jobs":ev_results,"tolerance_kwh":TOL}

def _result(scenario,dispatch,starts,policy,started,status,gap,message):
    # Decision-time schedules remain fixed. Replay observed irradiance ONLY after solving.
    # Grid and curtailment are balancing recourse; no retrospective job/battery optimization.
    for x in dispatch:
        x["grid_import_forecast_kwh"]=x["grid_import_kwh"]
        x["pv_used_forecast_kwh"]=x["pv_used_kwh"]
        if "solar_outcome_kwh" in x:
            net=x["fixed_load_kwh"]+x["ev_charge_kwh"]+x["batch_load_kwh"]+x["battery_charge_kwh"]-x["battery_discharge_kwh"]
            x["pv_available_kwh"]=x["solar_outcome_kwh"]
            x["pv_used_kwh"]=min(x["pv_available_kwh"],max(0,net))
            x["pv_curtail_kwh"]=x["pv_available_kwh"]-x["pv_used_kwh"]
            x["grid_import_kwh"]=max(0,net-x["pv_used_kwh"])
    constraints=check_constraints(scenario,dispatch,starts)
    emissions=sum(x["grid_import_kwh"]*x["ci_actual_g_per_kwh"] for x in dispatch)/1000
    predicted=sum(x["grid_import_forecast_kwh"]*x["ci_forecast_g_per_kwh"] for x in dispatch)/1000
    metrics={"emissions_kgco2":emissions,"forecast_emissions_kgco2":predicted,"cost_gbp":sum(x["grid_import_kwh"]*x["tariff_gbp_per_kwh"] for x in dispatch),"grid_import_kwh":sum(x["grid_import_kwh"] for x in dispatch),"pv_used_kwh":sum(x["pv_used_kwh"] for x in dispatch),"peak_grid_kw":max(x["grid_import_kwh"] for x in dispatch)/DT,"workload_kwh":sum(j.energy_kwh for j in scenario.ev_jobs+scenario.batch_jobs)}
    metrics["planning_peak_grid_kw"]=max(x["grid_import_forecast_kwh"] for x in dispatch)/DT
    metrics["zero_pv_peak_envelope_kw"]=max(x["fixed_load_kwh"]+x["ev_charge_kwh"]+x["batch_load_kwh"]+x["battery_charge_kwh"]-x["battery_discharge_kwh"] for x in dispatch)/DT
    metrics["peak_cap_exceedance_kw"]=max(0,metrics["peak_grid_kw"]-scenario.peak_cap_kw) if scenario.peak_cap_kw is not None else 0.0
    return {"policy":policy,"solver":{"name":"HiGHS/scipy.milp","scipy_version":scipy.__version__,"status":status,"success":constraints["verified"],"seconds":time.perf_counter()-started,"mip_gap":gap,"constraints_verified":constraints["verified"],"message":message,"objective_references":{"emissions_kgco2":50,"cost_gbp":100,"cycling_tie_breaker_per_kwh":1e-7}},"constraints":constraints,"dispatch":dispatch,"metrics":metrics,"batch_starts":starts}
