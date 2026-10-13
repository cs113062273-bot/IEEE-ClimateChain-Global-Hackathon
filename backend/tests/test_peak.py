import copy
import numpy as np
import pytest
from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import solve,check_constraints
from backend.app.services.data import prepare_intervals

@pytest.fixture
def inputs():return prepare_intervals("2025-08-12",Scenario())[0]

def test_default_legacy_numbers_unchanged(inputs):
    expected={"immediate":34.988672,"cost-first":35.23101939899275,"carbon-first":30.232687662313317,"hybrid":31.12381156658632,"oracle":29.885420110570696}
    for policy,emissions in expected.items():
        result=solve(Scenario(),inputs,policy)
        assert result["metrics"]["emissions_kgco2"]==pytest.approx(emissions,abs=1e-6)
        assert "peak_epigraph_kw" not in result["solver"]

def test_peak_weight_reduces_guard(inputs):
    old=solve(Scenario(),inputs,"hybrid")
    new=solve(Scenario(peak_weight=.2),inputs,"hybrid")
    assert new["constraints"]["verified"]
    assert new["metrics"]["zero_pv_peak_envelope_kw"]<=old["metrics"]["zero_pv_peak_envelope_kw"]+1e-6
    assert new["metrics"]["zero_pv_peak_envelope_kw"]<=new["solver"]["peak_epigraph_kw"]+1e-5

def test_guard_cap_survives_zero_actual_pv(inputs):
    changed=copy.deepcopy(inputs)
    for slot in changed:slot["solar_outcome_kwh"]=0
    scenario=Scenario(peak_cap_kw=40,peak_weight=.2)
    plan=solve(scenario,changed,"hybrid")
    assert plan["constraints"]["verified"]
    assert plan["metrics"]["peak_grid_kw"]<=40+1e-5
    assert plan["metrics"]["zero_pv_peak_envelope_kw"]<=40+1e-5

def test_guard_cap_infeasible_not_hidden(inputs):
    plan=solve(Scenario(battery_capacity_kwh=0,peak_cap_kw=5),inputs,"hybrid")
    assert plan["solver"]["status"]=="infeasible" and not plan["solver"]["success"]

def test_peak_first_does_not_use_any_forecast(inputs):
    first=solve(Scenario(),inputs,"peak-first")
    changed=copy.deepcopy(inputs)
    for t,slot in enumerate(changed):
        slot["ci_forecast_g_per_kwh"]=500+t
        slot["pv_available_kwh"]=99
        slot["pv_forecast_kwh"]=99
        slot["tariff_gbp_per_kwh"]=2+t/100
    second=solve(Scenario(),changed,"peak-first")
    assert first["constraints"]["verified"] and second["constraints"]["verified"]
    for a,b in zip(first["dispatch"],second["dispatch"]):
        for key in ["ev_charge_kwh","batch_load_kwh","battery_charge_kwh","battery_discharge_kwh"]:assert a[key]==pytest.approx(b[key],abs=1e-7)
        assert a["pv_forecast_kwh"]==b["pv_forecast_kwh"]==0

def test_peak_cap_constraint_reconstruction(inputs):
    plan=solve(Scenario(),inputs,"hybrid")
    constrained=Scenario(peak_cap_kw=25)
    assert not check_constraints(constrained,plan["dispatch"],plan["batch_starts"])["verified"]

def test_benchmark_reports_daily_mean_aggregate_and_negative_intervals():
    import pandas as pd
    from scripts.run_competition_benchmark import summary
    # Mean daily percentage is positive while total exposure grows: weighting
    # denominators matters, and the report must preserve this unfavorable result.
    rows=[]
    for date,baseline,exposure,difference in [("2025-09-01",100.,110.,-10.),("2025-09-02",10.,8.,20.)]:
        rows.append({"date":date,"policy":"example","paired_comparison_eligible":True,"constraints_verified":True,"baseline_valid":True,"solver_status":"optimal","candidate_constraint_violations":0,"wall_seconds":.1,"cpu_seconds":.1,"solver_seconds":.09,"mip_gap":0.,"process_peak_rss_mib":100.,"emissions_kgco2":exposure,"baseline_emissions_kgco2":baseline,"difference_percent":difference,"cost_gbp":20.,"cost_delta_gbp":1.,"peak_grid_kw":40.,"peak_delta_kw":5.,"peak_difference_percent":-14.2857})
    result=summary(pd.DataFrame(rows),["policy"])[0]
    assert result["mean_daily_difference_percent"]==pytest.approx(5)
    assert result["aggregate_difference_percent"]==pytest.approx(-100*8/110)
    assert result["non_improving_days"]==1
    assert result["iid_day_bootstrap_mean_95ci_percent"][0]<0
    assert result["cost_worsening_days"]==2 and result["peak_worsening_days"]==2

def test_benchmark_keeps_infeasible_pairs_without_savings():
    import pandas as pd
    from scripts.run_competition_benchmark import summary
    row={"date":"2025-09-01","policy":"infeasible","paired_comparison_eligible":False,"constraints_verified":False,"baseline_valid":False,"solver_status":"infeasible","candidate_constraint_violations":0,"wall_seconds":.1,"cpu_seconds":.1,"solver_seconds":.09,"mip_gap":None,"process_peak_rss_mib":100.}
    result=summary(pd.DataFrame([row]),["policy"])[0]
    assert result["valid_pairs"]==0 and result["policy_failed_days"]==result["baseline_failed_days"]==1
    assert "mean_daily_difference_percent" not in result
