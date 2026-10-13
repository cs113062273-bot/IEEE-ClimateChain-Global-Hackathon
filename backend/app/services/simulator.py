from __future__ import annotations
import hashlib,json,math
from backend.app.domain.solver import solve
from .data import prepare_intervals,envelope
from .storage import put

def compare(request,store=True):
    intervals,model=prepare_intervals(request.date,request.scenario)
    policies={"immediate":"immediate","cost_first":"cost-first","carbon_first":"carbon-first","hybrid":"hybrid","oracle":"oracle"}
    plans={key:solve(request.scenario,intervals,policy,request.carbon_weight,request.solver_time_limit_seconds) for key,policy in policies.items()}
    peak_scenario=request.scenario.model_copy(update={"peak_weight":request.scenario.peak_weight or .2})
    plans["peak_aware"]=solve(peak_scenario,intervals,"hybrid",request.carbon_weight,request.solver_time_limit_seconds)
    plans["peak_first"]=solve(request.scenario,intervals,"peak-first",request.carbon_weight,request.solver_time_limit_seconds)
    # Each evidence records the exact policy-specific objective, not only the shared assets.
    plans["peak_aware"]["scenario_parameters"]=peak_scenario.model_dump()
    plans["peak_first"]["scenario_parameters"]=request.scenario.model_dump()
    failures=[f"{key}: {plan['solver']['message']}" for key,plan in plans.items() if not plan["constraints"]["verified"]]
    if failures: raise ValueError("Scenario cannot yield a fair feasible comparison: "+"; ".join(failures))
    # All exposed replay input records use realized modeled PV, retaining separate forecast column.
    intervals=[{**x,"pv_available_kwh":x.get("solar_outcome_kwh",x["pv_available_kwh"])} for x in intervals]
    baseline=plans["immediate"]["metrics"]
    for key,plan in plans.items():
        if plan["metrics"] and baseline:
            m=plan["metrics"]; m["difference_kgco2"]=baseline["emissions_kgco2"]-m["emissions_kgco2"]
            m["difference_percent"]=100*m["difference_kgco2"]/baseline["emissions_kgco2"] if baseline["emissions_kgco2"] else None
            m["cost_delta_gbp"]=m["cost_gbp"]-baseline["cost_gbp"]
        plan["decision_information"]="perfect future actual CI; unrealistic oracle ceiling (calendar solar forecast still used)" if key=="oracle" else model["feature_policy"]
        plan["solar_replay"]="Forecast calendar PV at scheduling; observed reanalysis irradiance-derived modeled PV used only for outcome grid/curtailment recourse"
        if key=="peak_first":
            plan["decision_information"]="No carbon, tariff or solar forecasts enter decisions; zero-PV net-demand peak control"
            plan["solar_replay"]="Zero decision PV; shared observed-reanalysis irradiance-derived modeled PV used only for outcome grid/curtailment recourse"
    identity={"request":request.model_dump(),"intervals":intervals,"model":model}
    run_id="run-"+hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:20]
    errors=[x["ci_actual_g_per_kwh"]-x["ci_forecast_g_per_kwh"] for x in intervals]
    accuracy={"mae_g_per_kwh":sum(abs(x) for x in errors)/48,"rmse_g_per_kwh":math.sqrt(sum(x*x for x in errors)/48),"status":"retrospective outcome score; never a prediction feature"}
    value={"run_id":run_id,"date":request.date,"scenario":request.scenario.model_dump(),"intervals":intervals,"plans":plans,"forecast_model":model,"forecast_accuracy":accuracy,"carbon_weight":request.carbon_weight,**envelope(request.date)}
    if store: put(run_id,"run",value)
    return value
