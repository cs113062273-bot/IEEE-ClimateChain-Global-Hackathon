"""Audit controls must preserve workload, information boundaries and failures."""
import copy

import pytest

from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import solve
from backend.app.services.data import prepare_intervals
from scripts.audit_scheduler_competitiveness import heuristic, outcome_row, scenario_update, transformed


@pytest.mark.parametrize("policy", ["greedy_carbon", "greedy_cost", "peak_heuristic"])
def test_heuristics_complete_same_jobs_and_battery_endpoints(policy):
    scenario = Scenario(peak_weight=.2)
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    plan, error = heuristic(scenario, inputs, policy)
    assert error is None
    assert plan["constraints"]["verified"], plan["constraints"]
    row = outcome_row("2025-09-01", "nominal", policy, scenario, inputs, plan)
    assert row["valid"]
    assert row["delivered_workload_kwh"] == pytest.approx(62)
    assert row["unserved_workload_kwh"] == pytest.approx(0, abs=2e-5)
    assert row["terminal_soc_delta_kwh"] == pytest.approx(0, abs=2e-5)


def test_heuristic_decisions_cannot_see_future_carbon_or_solar():
    scenario = Scenario()
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    changed = copy.deepcopy(inputs)
    for x in changed:
        x["ci_actual_g_per_kwh"] = 1000
        x["solar_outcome_kwh"] = 0
    for policy in ["greedy_carbon", "greedy_cost", "peak_heuristic"]:
        first, _ = heuristic(scenario, inputs, policy)
        second, _ = heuristic(scenario, changed, policy)
        for a, b in zip(first["dispatch"], second["dispatch"]):
            for key in ["ev_charge_kwh", "batch_load_kwh", "battery_charge_kwh", "battery_discharge_kwh"]:
                assert a[key] == pytest.approx(b[key])


def test_unannounced_departure_retains_unserved_energy_and_disqualifies_savings():
    scenario = Scenario(peak_weight=.2)
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    planned, records, actual = transformed(scenario, inputs, "early_departure_unannounced", 0)
    plan = solve(planned, records, "hybrid")
    row = outcome_row("2025-09-01", "early_departure_unannounced", "gridproof_lightgbm", planned, records, plan, realized_scenario=actual)
    assert not row["valid"]
    assert row["unserved_workload_kwh"] > 0
    assert row["deadline_violations"] > 0


def test_greedy_infeasibility_is_not_a_zero_emission_winner():
    base = Scenario()
    jobs = [{**j.model_dump(), "deadline_slot":j.arrival_slot+1} for j in base.ev_jobs]
    scenario = scenario_update(base, {"ev_jobs":jobs})
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    plan, error = heuristic(scenario, inputs, "greedy_carbon")
    row = outcome_row("2025-09-01", "infeasible", "greedy_carbon", scenario, inputs, plan, error)
    assert plan is None and error
    assert not row["valid"]
    assert row["emissions_kgco2"] is None
    assert row["unserved_workload_kwh"] == 62


def test_import_guard_preserves_physical_cap_and_rejected_candidate_diagnostics():
    scenario = Scenario()
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    for x in inputs:
        x["fixed_load_kwh"] *= 2
    reference = solve(scenario, inputs, "hybrid")
    assert reference["solver"]["status"] == "fallback_immediate"
    rejected = reference["solver"]["rejected_candidate"]
    assert not rejected["constraints"]["verified"]
    assert rejected["max_grid_import_exceedance_kw"] > 0
    guarded = solve(scenario, inputs, "hybrid", robust_import_cap=True)
    assert guarded["constraints"]["verified"]
    assert guarded["solver"]["status"] != "fallback_immediate"
    assert guarded["metrics"]["zero_pv_peak_envelope_kw"] <= 60+1e-5
    assert all(job["completed"] for job in guarded["constraints"]["ev_jobs"])


def test_import_guard_cannot_hide_impossible_deadlines():
    base = Scenario()
    jobs = [{**j.model_dump(), "deadline_slot":j.arrival_slot+4} for j in base.ev_jobs]
    scenario = scenario_update(base, {"ev_jobs":jobs})
    inputs = prepare_intervals("2025-09-01", scenario)[0]
    plan = solve(scenario, inputs, "hybrid", robust_import_cap=True)
    assert plan["solver"]["status"] == "infeasible"
    assert not plan["dispatch"] and plan["metrics"] is None
