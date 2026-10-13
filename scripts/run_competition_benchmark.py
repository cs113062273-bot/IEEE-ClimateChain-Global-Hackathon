"""Phase-2 full locked test and matched controls. Writes competition_v2 only.

The configuration is recorded BEFORE execution, but this is not claimed to be
immutable preregistration: Phase-1 test outcomes were already inspected.
"""
from __future__ import annotations
import argparse,copy,ctypes,hashlib,json,math,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import solve
from backend.app.ml.forecast import seasonal
from backend.app.services.data import ROOT,ci_frame,prepare_intervals

OUT=ROOT/"experiments/competition_v2"
SEED=42
PEAK_WEIGHT=.2
MILP_CALLS=0
SENSITIVITIES=["battery_0kwh","battery_20kwh","battery_80kwh","battery_power_5kw","battery_power_20kw","fixed_load_half","fixed_load_150pct","fixed_load_double","ev_deadline_tighter","ev_deadline_infeasible","forecast_bias_plus30","forecast_noise_30g","forecast_timing_inverted","solar_20pct","efficiency_85pct","missing_forecast_rejected"]

def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def rss():
    if os.name=="nt":
        class Counters(ctypes.Structure):
            _fields_=[("cb",ctypes.c_ulong),("PageFaultCount",ctypes.c_ulong)]+[(k,ctypes.c_size_t) for k in ["PeakWorkingSetSize","WorkingSetSize","QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage","QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage"]]
        counters=Counters();counters.cb=ctypes.sizeof(counters)
        kernel=ctypes.WinDLL("kernel32",use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
        psapi=ctypes.WinDLL("psapi",use_last_error=True);psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):return counters.WorkingSetSize/1024**2,counters.PeakWorkingSetSize/1024**2
        return None,None
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=="darwin" else 1024)
        current=int(Path("/proc/self/statm").read_text().split()[1])*os.sysconf("SC_PAGE_SIZE")/1024**2 if Path("/proc/self/statm").exists() else None
        return current,peak
    except (ImportError,OSError):return None,None

def scenario_update(base,updates):return Scenario.model_validate({**base.model_dump(),**updates})

def configured_policies():
    # Tuple: output name, solver policy, forecast variant, carbon weight, peak weight, cap.
    return [
        ("immediate","immediate","lightgbm",.7,0,None),
        ("cost_first_no_ci","cost-first","lightgbm",0,0,None),
        ("carbon_lightgbm","carbon-first","lightgbm",1,0,None),
        ("hybrid_lightgbm","hybrid","lightgbm",.7,0,None),
        ("oracle_carbon","carbon-first","perfect_ci",1,0,None),
        ("hybrid_latest","hybrid","latest",.7,0,None),
        ("hybrid_seasonal","hybrid","seasonal",.7,0,None),
        ("hybrid_perfect_ci_matched","hybrid","perfect_ci",.7,0,None),
        ("carbon_latest","carbon-first","latest",1,0,None),
        ("carbon_seasonal","carbon-first","seasonal",1,0,None),
        ("peak_aware_lightgbm","hybrid","lightgbm",.7,PEAK_WEIGHT,None),
        ("peak_aware_latest","hybrid","latest",.7,PEAK_WEIGHT,None),
        ("peak_aware_seasonal","hybrid","seasonal",.7,PEAK_WEIGHT,None),
        ("peak_aware_perfect_ci_matched","hybrid","perfect_ci",.7,PEAK_WEIGHT,None),
        ("peak_first_no_forecasts","peak-first","lightgbm",0,0,None),
        ("peak_cap40_lightgbm","hybrid","lightgbm",.7,PEAK_WEIGHT,40),
        ("immediate_cap40","immediate","lightgbm",.7,0,40),
    ]

def make_config(days):
    return {"version":"competition-v2","recorded_utc":pd.Timestamp.now(tz="UTC").isoformat(),"seed":SEED,"training_window":["2025-01-08","2025-06-30"],"validation_window":["2025-07-01","2025-08-31"],"locked_test_window":["2025-09-01","2025-12-31"],"requested_days":days,"test_rule":"all 122 consecutive UTC days; --days only for development smoke","base_scenario":Scenario().model_dump(),"policy_definitions":configured_policies(),"peak_default_weight":PEAK_WEIGHT,"peak_default_rationale":"engineering tradeoff at fixed 60kW reference; fixed before this Phase2 test execution, not selected from test metrics","peak_guard":"worst-case zero PV; net load envelope bounds imports for all nonnegative solar outcomes","tradeoff_grid":{"carbon_weights":[0,.35,.7,1],"peak_weights":[0,.2,.5],"reference_kw":60,"policy_selection":"exploratory reported grid; never automatically choose a test-best deployment policy"},"sensitivities":SENSITIVITIES,"bootstrap":{"replicates":2000,"units":"days","moving_block_days":7,"seed":SEED,"negative_results":"preserved without clipping"},"solver":{"time_limit_seconds":10,"relative_mip_gap":1e-6,"native_threads":1,"persistent_worker":1},"preregistration_limit":"config is saved before this execution, not immutable preregistration; Phase1 test outcomes were already examined","publication_latency":"past actual timestamps assumed available; historical point-in-time/revision archives unavailable"}

def forecast_variants(intervals,past,issue):
    return {"lightgbm":np.array([x["ci_forecast_g_per_kwh"] for x in intervals]),"latest":np.full(48,float(past.grid_ci_actual_g_per_kwh.dropna().iloc[-1])),"seasonal":seasonal(past,issue),"perfect_ci":np.array([x["ci_actual_g_per_kwh"] for x in intervals])}

def with_forecast(intervals,values):return [{**x,"ci_forecast_g_per_kwh":float(values[t])} for t,x in enumerate(intervals)]

def measured(date,name,scenario,intervals,solver_policy,carbon_weight,forecast,baseline=None,case="nominal"):
    start=time.perf_counter();cpu_start=time.process_time()
    try:
        plan=solve(scenario,intervals,solver_policy,carbon_weight,10)
        metrics=plan["metrics"];valid=plan["constraints"]["verified"]
        status=plan["solver"]["status"];message=plan["solver"].get("message");gap=plan["solver"].get("mip_gap")
        violations=len(plan["constraints"]["violations"]) if plan["dispatch"] else 0
        solver_seconds=plan["solver"]["seconds"]
    except (ValueError,TypeError,KeyError) as exc:
        metrics=None;valid=False;status="input_rejected";message=str(exc);gap=None;violations=0;solver_seconds=None
    current,peak=rss()
    effective_weight=1 if solver_policy in ("carbon-first","oracle") else 0 if solver_policy in ("cost-first","peak-first","immediate") else carbon_weight
    row={"date":date,"case":case,"policy":name,"solver_policy":solver_policy,"forecast_variant":forecast,"carbon_weight":carbon_weight,"effective_carbon_weight":effective_weight,"peak_weight":scenario.peak_weight,"peak_cap_kw":scenario.peak_cap_kw,"peak_risk_mode":scenario.peak_risk_mode,"scenario_sha256":fingerprint(scenario.model_dump()),"inputs_sha256":fingerprint(intervals),"solver_status":status,"solver_message":message,"constraints_verified":valid,"candidate_constraint_violations":violations,"mip_gap":gap,"solver_seconds":solver_seconds,"wall_seconds":time.perf_counter()-start,"cpu_seconds":time.process_time()-cpu_start,"rss_after_mib":current,"process_peak_rss_mib":peak}
    for key in ["emissions_kgco2","cost_gbp","peak_grid_kw","planning_peak_grid_kw","zero_pv_peak_envelope_kw","grid_import_kwh","workload_kwh"]:row[key]=metrics.get(key) if metrics else None
    row["baseline_valid"]=bool(baseline and baseline["constraints_verified"])
    for key in ["emissions_kgco2","cost_gbp","peak_grid_kw"]:row["baseline_"+key]=baseline[key] if baseline else None
    eligible=valid and row["baseline_valid"]
    row["paired_comparison_eligible"]=eligible
    row["difference_percent"]=100*(baseline["emissions_kgco2"]-metrics["emissions_kgco2"])/baseline["emissions_kgco2"] if eligible and baseline["emissions_kgco2"] else None
    row["cost_delta_gbp"]=metrics["cost_gbp"]-baseline["cost_gbp"] if eligible else None
    row["peak_delta_kw"]=metrics["peak_grid_kw"]-baseline["peak_grid_kw"] if eligible else None
    row["peak_difference_percent"]=100*(baseline["peak_grid_kw"]-metrics["peak_grid_kw"])/baseline["peak_grid_kw"] if eligible and baseline["peak_grid_kw"] else None
    return row

def attach_baseline(row,baseline):
    row=dict(row);row["baseline_valid"]=baseline["constraints_verified"]
    for key in ["emissions_kgco2","cost_gbp","peak_grid_kw"]:row["baseline_"+key]=baseline[key]
    eligible=row["constraints_verified"] and row["baseline_valid"];row["paired_comparison_eligible"]=eligible
    row["difference_percent"]=100*(baseline["emissions_kgco2"]-row["emissions_kgco2"])/baseline["emissions_kgco2"] if eligible and baseline["emissions_kgco2"] else None
    row["cost_delta_gbp"]=row["cost_gbp"]-baseline["cost_gbp"] if eligible else None
    row["peak_delta_kw"]=row["peak_grid_kw"]-baseline["peak_grid_kw"] if eligible else None
    row["peak_difference_percent"]=100*(baseline["peak_grid_kw"]-row["peak_grid_kw"])/baseline["peak_grid_kw"] if eligible and baseline["peak_grid_kw"] else None
    return row

def summary(frame,group_keys):
    results=[]
    for label,group in frame.groupby(group_keys,dropna=False,sort=False):
        labels=label if isinstance(label,tuple) else (label,);entry=dict(zip(group_keys,labels));eligible=group.loc[group.paired_comparison_eligible].sort_values("date")
        entry.update({"attempted_days":len(group),"valid_pairs":len(eligible),"policy_failed_days":int((~group.constraints_verified).sum()),"baseline_failed_days":int((~group.baseline_valid).sum()),"fallback_days":int((group.solver_status=="fallback_immediate").sum()),"candidate_constraint_violations":int(group.candidate_constraint_violations.sum()),"mean_wall_seconds":float(group.wall_seconds.mean()),"p95_wall_seconds":float(group.wall_seconds.quantile(.95)),"max_wall_seconds":float(group.wall_seconds.max()),"mean_cpu_seconds":float(group.cpu_seconds.mean()),"mean_solver_seconds":float(group.solver_seconds.mean()) if group.solver_seconds.notna().any() else None,"max_mip_gap":float(group.mip_gap.max()) if group.mip_gap.notna().any() else None,"process_peak_rss_mib":float(group.process_peak_rss_mib.max()) if group.process_peak_rss_mib.notna().any() else None})
        if len(eligible):
            differences=eligible.difference_percent.to_numpy();E=eligible.emissions_kgco2.to_numpy();B=eligible.baseline_emissions_kgco2.to_numpy();n=len(E);rng=np.random.default_rng(SEED)
            indices=rng.integers(0,n,size=(2000,n));means=differences[indices].mean(axis=1);aggregate=100*(B[indices].sum(axis=1)-E[indices].sum(axis=1))/B[indices].sum(axis=1)
            block_starts=rng.integers(0,n,size=(2000,math.ceil(n/7)));blocks=((block_starts[:,:,None]+np.arange(7))%n).reshape(2000,-1)[:,:n];block_means=differences[blocks].mean(axis=1)
            entry.update({"mean_emissions_kgco2":float(E.mean()),"total_emissions_kgco2":float(E.sum()),"baseline_total_emissions_kgco2":float(B.sum()),"aggregate_difference_percent":float(100*(B.sum()-E.sum())/B.sum()),"mean_daily_difference_percent":float(differences.mean()),"median_daily_difference_percent":float(np.median(differences)),"daily_difference_std_percentage_points":float(np.std(differences,ddof=1)) if n>1 else None,"p10_daily_difference_percent":float(np.quantile(differences,.1)),"p90_daily_difference_percent":float(np.quantile(differences,.9)),"non_improving_days":int((differences<=0).sum()),"iid_day_bootstrap_mean_95ci_percent":[float(np.quantile(means,.025)),float(np.quantile(means,.975))],"iid_day_bootstrap_aggregate_95ci_percent":[float(np.quantile(aggregate,.025)),float(np.quantile(aggregate,.975))],"circular_7day_block_mean_95ci_percent":[float(np.quantile(block_means,.025)),float(np.quantile(block_means,.975))],"mean_cost_gbp":float(eligible.cost_gbp.mean()),"mean_cost_delta_gbp":float(eligible.cost_delta_gbp.mean()),"mean_peak_grid_kw":float(eligible.peak_grid_kw.mean()),"mean_peak_delta_kw":float(eligible.peak_delta_kw.mean()),"mean_peak_difference_percent":float(eligible.peak_difference_percent.mean()),"carbon_worsening_days":int((differences<0).sum()),"cost_worsening_days":int((eligible.cost_delta_gbp>1e-8).sum()),"peak_worsening_days":int((eligible.peak_delta_kw>1e-8).sum())})
        else:entry["comparison_status"]="No valid paired comparison; failures retained, no savings claimed"
        results.append(entry)
    return results

def perturb(base,inputs,case,day_index):
    scenario=base;records=copy.deepcopy(inputs)
    if case.startswith("battery_") and case.endswith("kwh"):scenario=scenario_update(base,{"battery_capacity_kwh":float(case.split("_")[1].removesuffix("kwh"))})
    elif case.startswith("battery_power"):power=float(case.split("_")[2].removesuffix("kw"));scenario=scenario_update(base,{"charge_kw":power,"discharge_kw":power})
    elif case.startswith("fixed_load"):
        scale={"fixed_load_half":.5,"fixed_load_150pct":1.5,"fixed_load_double":2}[case]
        for record in records:record["fixed_load_kwh"]*=scale
    elif case.startswith("ev_deadline"):
        jobs=[j.model_dump() for j in base.ev_jobs]
        for job in jobs:job["deadline_slot"]=job["arrival_slot"]+(4 if case.endswith("infeasible") else 10)
        scenario=scenario_update(base,{"ev_jobs":jobs})
    elif case=="efficiency_85pct":scenario=scenario_update(base,{"eta_charge":.85,"eta_discharge":.85})
    elif case=="solar_20pct":
        for record in records:
            for key in ["pv_available_kwh","pv_forecast_kwh","solar_outcome_kwh"]:record[key]*=.2
    elif case=="forecast_bias_plus30":
        for record in records:record["ci_forecast_g_per_kwh"]*=1.3
    elif case=="forecast_noise_30g":
        noise=np.random.default_rng(SEED+day_index).normal(0,30,48)
        for record,value in zip(records,noise):record["ci_forecast_g_per_kwh"]=float(np.clip(record["ci_forecast_g_per_kwh"]+value,0,1500))
    elif case=="forecast_timing_inverted":
        values=[r["ci_forecast_g_per_kwh"] for r in records]
        for record,value in zip(records,reversed(values)):record["ci_forecast_g_per_kwh"]=value
    elif case=="missing_forecast_rejected":records[8]["ci_forecast_g_per_kwh"]=None
    else:raise ValueError(case)
    return scenario,records

def main():
    global MILP_CALLS
    parser=argparse.ArgumentParser();parser.add_argument("--days",type=int,default=122);parser.add_argument("--skip-sensitivity",action="store_true");parser.add_argument("--skip-tradeoff",action="store_true");args=parser.parse_args()
    if not 1<=args.days<=122:raise ValueError("days must be1..122")
    OUT.mkdir(parents=True,exist_ok=True);config=make_config(args.days)
    source_paths=["data/processed/neso_ci_2025.csv","data/processed/intervals_2025.csv","data/sample/intervals.json","backend/app/domain/solver.py","backend/app/domain/schemas.py","backend/app/services/data.py","backend/app/ml/forecast.py","scripts/run_competition_benchmark.py","experiments/models_portable/carbon_model.json"]
    config["execution_snapshots"]=[{"path":relative,"sha256":hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()} for relative in source_paths if (ROOT/relative).exists()]
    config["skip_sensitivity"]=args.skip_sensitivity;config["skip_tradeoff"]=args.skip_tradeoff
    (OUT/"frozen_config.json").write_text(json.dumps(config,indent=2),encoding="utf-8")
    (OUT/"frozen_config.sha256").write_text(fingerprint(config)+"\n",encoding="ascii")
    import backend.app.domain.solver as solver_module
    native_milp=solver_module.milp
    def counted_milp(*args,**kwargs):
        global MILP_CALLS
        MILP_CALLS+=1
        return native_milp(*args,**kwargs)
    solver_module.milp=counted_milp
    started=time.perf_counter();cpu_start=time.process_time();frame=ci_frame();base=Scenario();raw=[];grid=[];sensitivity=[];validation=[];failures=[]
    dates=pd.date_range("2025-09-01","2025-12-31",tz="UTC",freq="D")[:args.days]
    legacy_predictions=pd.read_csv(ROOT/"experiments/forecast_predictions.csv");legacy_predictions=legacy_predictions.loc[legacy_predictions.method=="lightgbm_past_only"].copy();legacy_predictions["date"]=legacy_predictions.decision_time.str[:10]
    legacy_lookup={date:group.sort_values("outcome_time").forecast_g_per_kwh.to_numpy() for date,group in legacy_predictions.groupby("date")}
    portable_diffs=[]
    for day_index,issue in enumerate(dates):
        date=issue.date().isoformat()
        try:
            inputs,metadata=prepare_intervals(date,base,frame)
            if metadata["version"]!="lightgbm-past-only-v1":raise ValueError("Frozen LightGBM artifact unavailable; refusing to label seasonal fallback as ML")
        except ValueError as exc:failures.append({"date":date,"status":"input_rejected","reason":str(exc)});continue
        variants=forecast_variants(inputs,frame.loc[frame.index<issue],issue)
        if date in legacy_lookup:portable_diffs.append(float(np.max(np.abs(variants["lightgbm"]-legacy_lookup[date]))))
        baseline=measured(date,"immediate",base,inputs,"immediate",.7,"lightgbm")
        cache={}
        for name,policy,forecast,weight,peak_weight,cap in configured_policies():
            scenario=scenario_update(base,{"peak_weight":peak_weight,"peak_cap_kw":cap});records=with_forecast(inputs,variants[forecast])
            if name=="immediate":row=attach_baseline(baseline,baseline)
            else:
                matched=baseline if cap is None else measured(date,"matched_immediate_cap40",scenario,records,"immediate",weight,forecast)
                row=measured(date,name,scenario,records,policy,weight,forecast,matched)
            raw.append(row);cache[(forecast,policy,weight,peak_weight,cap)]=row
        if not args.skip_tradeoff:
            for weight in config["tradeoff_grid"]["carbon_weights"]:
                for peak_weight in config["tradeoff_grid"]["peak_weights"]:
                    key=("lightgbm","hybrid",weight,peak_weight,None);name=f"carbon{weight:g}_peak{peak_weight:g}"
                    row=cache.get(key) or measured(date,name,scenario_update(base,{"peak_weight":peak_weight}),inputs,"hybrid",weight,"lightgbm",baseline,case="tradeoff_grid")
                    grid.append({**row,"case":"tradeoff_grid","policy":name})
        if not args.skip_sensitivity:
            for case in SENSITIVITIES:
                altered,records=perturb(base,inputs,case,day_index)
                matched=measured(date,"immediate",altered,records,"immediate",.7,"lightgbm",case=case);sensitivity.append(attach_baseline(matched,matched))
                for name,policy,peak_weight in [("cost_first_no_ci","cost-first",0),("hybrid_lightgbm","hybrid",0),("peak_aware_lightgbm","hybrid",PEAK_WEIGHT),("peak_first_no_forecasts","peak-first",0)]:
                    sensitivity.append(measured(date,name,scenario_update(altered,{"peak_weight":peak_weight}),records,policy,.7,"lightgbm",matched,case=case))
        print(f"Completed locked day {day_index+1}/{len(dates)} {date}",flush=True)
    # Validation diagnostics use the already-frozen June-trained candidate,
    # NOT a selection made using later validation outcomes in a historical UI.
    for date,values in legacy_lookup.items():
        if not "2025-07-01"<=date<"2025-09-01":continue
        try:inputs,_=prepare_intervals(date,base,frame)
        except ValueError as exc:failures.append({"date":date,"split":"validation","status":"input_rejected","reason":str(exc)});continue
        records=with_forecast(inputs,values);baseline=measured(date,"immediate",base,records,"immediate",.7,"frozen_training_candidate",case="validation_candidate")
        for peak_weight in [0,PEAK_WEIGHT,.5]:validation.append(measured(date,f"peak_weight_{peak_weight:g}",scenario_update(base,{"peak_weight":peak_weight}),records,"hybrid",.7,"frozen_training_candidate",baseline,case="validation_candidate"))
    frames={"daily_results":pd.DataFrame(raw),"tradeoff_grid":pd.DataFrame(grid),"sensitivities":pd.DataFrame(sensitivity),"validation_diagnostics":pd.DataFrame(validation)}
    for name,table in frames.items():
        if len(table):table.to_csv(OUT/(name+".csv"),index=False)
    summaries={"policies":summary(frames["daily_results"],["policy"]),"tradeoff_grid":summary(frames["tradeoff_grid"],["policy"]) if len(grid) else [],"sensitivities":summary(frames["sensitivities"],["case","policy"]) if len(sensitivity) else [],"validation_diagnostics":summary(frames["validation_diagnostics"],["policy"]) if len(validation) else []}
    report={"status":"computed","config_sha256":fingerprint(config),"requested_test_days":len(dates),"completed_test_days":frames["daily_results"].date.nunique(),"input_failures":failures,"forecast_portable_vs_original_max_abs_g_per_kwh":max(portable_diffs) if portable_diffs else None,"execution":{"wall_seconds":time.perf_counter()-started,"cpu_seconds":time.process_time()-cpu_start,"native_milp_calls":MILP_CALLS,"rows":{k:len(v) for k,v in frames.items()},"rss_after_mib":rss()[0],"process_peak_rss_mib":rss()[1],"ram_scope":"whole benchmark process, Python+native libraries+cached data; per-row process peak is cumulative, not isolated solver allocation"},**summaries,"limitations":["simulation, not measured campus or causal avoided emissions","average national GB intensity; tariff illustrative","perfect-CI comparator still calendar solar planning with outcome recourse; not a strict realized-outcome optimality ceiling","all122 locked Q4 days, not an unseen four-season test","daily battery reset; no multiday continuous scheduling","strict complete-input contract rejects missing forecast even for objective-independent controls","Phase1 outcomes were known before Phase2 design; no immutable preregistration claimed","no test-best automatic deployment policy selection"]}
    (OUT/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"completed_days":report["completed_test_days"],"execution":report["execution"],"config_sha256":report["config_sha256"]},indent=2),flush=True)

if __name__=="__main__":main()
