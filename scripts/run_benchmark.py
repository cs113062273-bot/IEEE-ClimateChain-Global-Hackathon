"""Locked Sept-Dec daily scheduling evaluation; day bootstrap and failure cases."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse,json
import numpy as np
import pandas as pd
from backend.app.services.data import ROOT,ci_frame,prepare_intervals
from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import solve

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--days",type=int,default=24);args=parser.parse_args()
    if args.days<2 or args.days>122: raise ValueError("days must be 2..122")
    frame=ci_frame();dates=pd.date_range("2025-09-01","2025-12-31",tz="UTC",freq="D")
    chosen=dates[np.unique(np.linspace(0,len(dates)-1,args.days,dtype=int))]
    scenario=Scenario();rows=[];robust=[]
    for issue in chosen:
        date=issue.date().isoformat()
        try: intervals,model=prepare_intervals(date,scenario,frame)
        except ValueError as e:
            print(f"Skipped {date}: {e}");continue
        plans={policy:solve(scenario,intervals,policy,.7,10) for policy in ["immediate","cost-first","carbon-first","hybrid","oracle"]}
        baseline=plans["immediate"]["metrics"]
        for policy,plan in plans.items():
            if not plan["metrics"]: raise RuntimeError(f"Infeasible benchmark {date} {policy}: {plan['solver']}")
            m=plan["metrics"]
            rows.append({"date":date,"policy":policy,"forecast":model["version"],"baseline_emissions_kgco2":baseline["emissions_kgco2"],"emissions_kgco2":m["emissions_kgco2"],"difference_percent":100*(baseline["emissions_kgco2"]-m["emissions_kgco2"])/baseline["emissions_kgco2"],"cost_gbp":m["cost_gbp"],"cost_delta_gbp":m["cost_gbp"]-baseline["cost_gbp"],"violations":len(plan["constraints"]["violations"]),"solver_seconds":plan["solver"]["seconds"],"solver_status":plan["solver"]["status"],"workload_kwh":m["workload_kwh"]})
        # Forecast timing inversion stresses genuine non-improvement without changing measured outcomes.
        for name in ["forecast_bias_plus30","forecast_timing_inverted","battery_efficiency_85","solar_low_20pct","missing_ci_rejected"]:
            changed=[dict(x) for x in intervals]; altered=scenario
            if name=="forecast_bias_plus30":
                for x in changed: x["ci_forecast_g_per_kwh"]*=1.3
            elif name=="forecast_timing_inverted":
                values=[x["ci_forecast_g_per_kwh"] for x in changed]
                for x,v in zip(changed,reversed(values)):x["ci_forecast_g_per_kwh"]=v
            elif name=="battery_efficiency_85": altered=scenario.model_copy(update={"eta_charge":.85,"eta_discharge":.85})
            elif name=="solar_low_20pct":
                for x in changed:x["pv_available_kwh"]*=.2;x["solar_outcome_kwh"]*=.2;x["pv_forecast_kwh"]*=.2
            else: changed[8]["ci_forecast_g_per_kwh"]=None
            try:
                b=solve(altered,changed,"immediate");p=solve(altered,changed,"carbon-first")
                diff=100*(b["metrics"]["emissions_kgco2"]-p["metrics"]["emissions_kgco2"])/b["metrics"]["emissions_kgco2"]
                robust.append({"date":date,"case":name,"difference_percent":diff,"emissions_kgco2":p["metrics"]["emissions_kgco2"],"violations":len(p["constraints"]["violations"]),"status":p["solver"]["status"]})
            except ValueError as e:
                robust.append({"date":date,"case":name,"difference_percent":None,"emissions_kgco2":None,"violations":None,"status":"rejected","reason":str(e)})
        print(f"Completed {date}")
    result=pd.DataFrame(rows);sensitivity=pd.DataFrame(robust);output=ROOT/"experiments";output.mkdir(exist_ok=True)
    result.to_csv(output/"replay_results.csv",index=False);sensitivity.to_csv(output/"robustness.csv",index=False)
    rng=np.random.default_rng(42);summaries=[]
    for policy,group in result.groupby("policy",sort=False):
        diffs=group.difference_percent.to_numpy();means=np.mean(rng.choice(diffs,size=(2000,len(diffs)),replace=True),axis=1)
        summaries.append({"policy":policy,"days":len(group),"mean_difference_percent":float(np.mean(diffs)),"median_difference_percent":float(np.median(diffs)),"p10_percent":float(np.quantile(diffs,.1)),"p90_percent":float(np.quantile(diffs,.9)),"day_bootstrap_95ci_percent":[float(np.quantile(means,.025)),float(np.quantile(means,.975))],"mean_cost_delta_gbp":float(group.cost_delta_gbp.mean()),"non_improving_days":int((diffs<=0).sum()),"violations":int(group.violations.sum()),"mean_solver_seconds":float(group.solver_seconds.mean()),"max_solver_seconds":float(group.solver_seconds.max())})
    pd.DataFrame(summaries).to_csv(output/"baseline_comparison.csv",index=False)
    report={"status":"computed","seed":42,"locked_test_window":["2025-09-01","2025-12-31"],"sample_rule":f"{args.days} equally spaced UTC days, selected before solving","actual_days":result.date.nunique(),"policies":summaries,"forecast_information":"past-only at midnight; perfect future actual reserved for oracle","pv_information":"calendar forecast for scheduling; observed reanalysis radiation-derived modeled PV used only after scheduling for grid/curtailment replay recourse; same assumptions across policies","immediate_battery_rule":"idle, initial=terminal SoC, PV self consumption","day_bootstrap_samples":2000,"robustness_non_improvements":int((sensitivity.difference_percent<=0).sum()),"robustness_cases":sorted(sensitivity.case.unique()),"limitations":["sampled held-out days, not field trial","illustrative tariffs","no causal emissions abatement or carbon credits","one site template and one year"]}
    (output/"benchmark_summary.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
