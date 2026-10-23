"""Matched, past-only scheduler audit using the distributed pinned snapshots.

Extends the existing benchmark/checker, leaving competition_v2 and production
policy defaults untouched. All heuristics can use the same battery and workloads.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.domain.schemas import Scenario
from backend.app.domain.solver import DT, T, TOL, _dispatch, _result, check_constraints, solve
from backend.app.ml.forecast import seasonal
from backend.app.services.data import prepare_intervals
from backend.app.services.lineage import _trusted_bytes
from scripts.run_competition_benchmark import fingerprint, perturb, scenario_update

POLICIES = ["immediate", "greedy_carbon", "greedy_cost", "peak_heuristic",
            "gridproof_lightgbm", "gridproof_seasonal", "gridproof_oracle"]
CASES = ["nominal", "solar_20pct", "unforecast_carbon_spike", "demand_surge",
         "early_departure_known", "short_window", "early_departure_unannounced", "impossible_window"]


def pinned_data():
    anchors = json.loads((ROOT / "data/trust/source_anchors.v1.json").read_text())
    carbon = json.loads(_trusted_bytes(anchors["sources"]["neso-national-ci-2025"]))
    weather = json.loads(_trusted_bytes(anchors["sources"]["openmeteo-london-weather-2025"]))["hourly"]
    radiation = dict(zip(pd.to_datetime(weather["time"], utc=True), weather["shortwave_radiation"]))
    rows = []
    for row in carbon["result"]["records"]:
        start = pd.Timestamp(row["datetime"], tz="UTC")
        rows.append({"start_utc":start.isoformat().replace("+00:00", "Z"),
                     "end_utc":(start + pd.Timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
                     "grid_ci_actual_g_per_kwh":float(row["actual"]) if row["actual"] is not None else None,
                     "grid_ci_forecast_g_per_kwh":float(row["forecast"]) if row["forecast"] is not None else None,
                     "shortwave_radiation_w_per_m2":radiation[start.floor("h") + pd.Timedelta(hours=1)]})
    frame = pd.DataFrame(rows)
    frame["start_utc"] = pd.to_datetime(frame.start_utc, utc=True)
    frame = frame.set_index("start_utc")
    # Preserve sample metadata on the four original demo days. Other days have
    # the same default provenance as the original full normalized CSV.
    sample = json.loads((ROOT / "data/sample/intervals.json").read_text(encoding="utf-8-sig"))
    samples = {x["start_utc"]:x for x in sample["intervals"]}
    rows = [samples.get(x["start_utc"], x) for x in rows]
    by_day = {}
    for row in rows:
        by_day.setdefault(row["start_utc"][:10], []).append(row)
    return frame, by_day, anchors


def day_inputs(date, scenario, frame, by_day):
    # Only source loading is injected; production forecasting, load, tariff and
    # PV transformations run unchanged. No cache/manifests are overwritten.
    with patch("backend.app.services.data.fixture", return_value={"intervals":by_day[date]}):
        inputs, metadata = prepare_intervals(date, scenario, frame)
    if metadata["version"] != "lightgbm-past-only-v1":
        raise ValueError("Frozen LightGBM model required; refusing mislabeled fallback")
    return inputs


from backend.app.domain.baselines import heuristic


def outcome_row(date, case, policy, scenario, inputs, plan, error=None, realized_scenario=None):
    target = realized_scenario or scenario
    required = sum(j.energy_kwh for j in target.ev_jobs+target.batch_jobs)
    row = {"date":date, "case":case, "policy":policy, "scenario_sha256":fingerprint(scenario.model_dump()),
           "realized_scenario_sha256":fingerprint(target.model_dump()), "inputs_sha256":fingerprint(inputs),
           "required_workload_kwh":required, "delivered_workload_kwh":0., "unserved_workload_kwh":required,
           "capacity_violations":0, "deadline_violations":0, "returned_constraint_violations":0,
           "valid":False, "status":error or "unavailable", "emissions_kgco2":None, "cost_gbp":None,
           "peak_grid_kw":None, "solver_seconds":None, "candidate_rejected":False}
    if not plan or not plan["dispatch"]:
        if plan:
            row["status"] = plan["solver"]["status"]
            row["reason"] = plan["solver"].get("message")
        return row
    records = copy.deepcopy(plan["dispatch"])
    # Unexpected departure: no clairvoyant reoptimization or battery changes.
    # Charging after actual departure cannot count as delivered or as savings.
    for t, x in enumerate(records):
        for j, job in enumerate(target.ev_jobs):
            if not job.arrival_slot <= t < job.deadline_slot:
                x["ev_by_job_kwh"][j] = 0.
        x["ev_charge_kwh"] = sum(x["ev_by_job_kwh"])
        net = x["fixed_load_kwh"]+x["ev_charge_kwh"]+x["batch_load_kwh"]+x["battery_charge_kwh"]-x["battery_discharge_kwh"]
        x["pv_used_kwh"] = min(x["pv_available_kwh"], max(0, net))
        x["pv_curtail_kwh"] = x["pv_available_kwh"]-x["pv_used_kwh"]
        x["grid_import_kwh"] = max(0, net-x["pv_used_kwh"])
    check = check_constraints(target, records, plan["batch_starts"])
    delivered = sum(x["ev_charge_kwh"]+x["batch_load_kwh"] for x in records)
    row.update({"delivered_workload_kwh":delivered, "unserved_workload_kwh":max(0, required-delivered),
                "valid":check["verified"], "status":plan["solver"]["status"],
                "returned_constraint_violations":len(check["violations"]),
                "capacity_violations":sum("cap" in v.lower() or "power" in v.lower() for v in check["violations"]),
                "deadline_violations":sum(sum(x["ev_by_job_kwh"][j] for x in records[:job.deadline_slot])+TOL < job.energy_kwh
                                          for j, job in enumerate(target.ev_jobs)),
                "reason":"; ".join(check["violations"]), "solver_seconds":plan["solver"]["seconds"],
                "candidate_rejected":"candidate failed" in plan["solver"].get("message", "").lower(),
                "emissions_kgco2":sum(x["grid_import_kwh"]*x["ci_actual_g_per_kwh"] for x in records)/1000,
                "cost_gbp":sum(x["grid_import_kwh"]*x["tariff_gbp_per_kwh"] for x in records),
                "peak_grid_kw":max(x["grid_import_kwh"] for x in records)/DT,
                "terminal_soc_delta_kwh":records[-1]["soc_end_kwh"]-records[0]["soc_start_kwh"]})
    return row


def transformed(base, inputs, case, day_index):
    if case == "solar_20pct":
        scenario, records = perturb(base, inputs, case, day_index)
    else:
        scenario, records = base, copy.deepcopy(inputs)
    realized = None
    if case == "unforecast_carbon_spike":
        # Synthetic outcome shock only. Forecasts and every decision stay fixed.
        for t in range(28,36):
            records[t]["ci_actual_g_per_kwh"] = min(1500, records[t]["ci_actual_g_per_kwh"]+200)
    elif case == "demand_surge":
        jobs = [{**j.model_dump(), "energy_kwh":j.energy_kwh*2} for j in base.ev_jobs]
        scenario = scenario_update(base, {"ev_jobs":jobs})
        for x in records:
            x["fixed_load_kwh"] *= 2
    elif case in ("early_departure_known", "early_departure_unannounced"):
        jobs = [{**j.model_dump(), "deadline_slot":j.arrival_slot+6} for j in base.ev_jobs]
        changed = scenario_update(base, {"ev_jobs":jobs})
        if case == "early_departure_known":
            scenario = changed
        else:
            realized = changed
    elif case == "short_window":
        jobs = [{**j.model_dump(), "arrival_slot":j.deadline_slot-5} for j in base.ev_jobs]
        scenario = scenario_update(base, {"ev_jobs":jobs})
    elif case == "impossible_window":
        jobs = [{**j.model_dump(), "deadline_slot":j.arrival_slot+4} for j in base.ev_jobs]
        scenario = scenario_update(base, {"ev_jobs":jobs})
    return scenario, records, realized


def block_ci(values):
    values = np.asarray(values)
    rng = np.random.default_rng(42)
    starts = rng.integers(0, len(values), size=(2000, int(np.ceil(len(values)/7))))
    indices = ((starts[:,:,None]+np.arange(7)) % len(values)).reshape(2000,-1)[:,:len(values)]
    return np.quantile(values[indices].mean(axis=1), [.025,.975]).tolist()


def summarize(frame):
    entries = []
    for (case, policy), group in frame.groupby(["case", "policy"], sort=False):
        baseline = frame[(frame.case == case) & (frame.policy == "immediate")].set_index("date")
        valid = group[group.valid].set_index("date")
        pair = valid.join(baseline[["valid", "emissions_kgco2", "cost_gbp", "peak_grid_kw"]], rsuffix="_baseline")
        pair = pair[pair.valid_baseline]
        entry = {"case":case, "policy":policy, "attempted":len(group), "valid_days":int(group.valid.sum()),
                 "valid_pairs":len(pair), "incomplete_days":int((group.unserved_workload_kwh>TOL).sum()),
                 "total_unserved_kwh":float(group.unserved_workload_kwh.sum()),
                 "capacity_violations":int(group.capacity_violations.sum()),
                 "deadline_violations":int(group.deadline_violations.sum()),
                 "fallback_days":int((group.status == "fallback_immediate").sum())}
        if len(pair):
            differences = 100*(pair.emissions_kgco2_baseline-pair.emissions_kgco2)/pair.emissions_kgco2_baseline
            entry.update({"mean_emissions_kgco2":float(pair.emissions_kgco2.mean()), "mean_cost_gbp":float(pair.cost_gbp.mean()),
                          "mean_peak_kw":float(pair.peak_grid_kw.mean()), "mean_delivered_kwh":float(pair.delivered_workload_kwh.mean()),
                          "aggregate_carbon_improvement_pct":float(100*(pair.emissions_kgco2_baseline.sum()-pair.emissions_kgco2.sum())/pair.emissions_kgco2_baseline.sum()),
                          "mean_daily_carbon_improvement_pct":float(differences.mean()),
                          "block_95ci_mean_daily_pct":block_ci(differences),
                          "carbon_worsening_days":int((differences < -1e-8).sum()),
                          "cost_improvement_pct":float(100*(1-pair.cost_gbp.sum()/pair.cost_gbp_baseline.sum())),
                          "peak_improvement_pct":float(100*(1-pair.peak_grid_kw.mean()/pair.peak_grid_kw_baseline.mean()))})
        entries.append(entry)
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=122)
    parser.add_argument("--out", type=Path, default=ROOT/"experiments/competitiveness_audit")
    args = parser.parse_args()
    if not 1 <= args.days <= 122:
        raise ValueError("days must be 1..122")
    args.out.mkdir(parents=True, exist_ok=True)
    frame, by_day, anchors = pinned_data()
    base = Scenario(peak_weight=.2)
    files = ["backend/app/domain/solver.py", "backend/app/domain/schemas.py", "backend/app/ml/forecast.py",
             "backend/app/services/data.py", "scripts/audit_scheduler_competitiveness.py", "experiments/models_portable/carbon_model.json",
             "experiments/competition_v2/daily_results.csv", "data/sample/upstream/neso_ci_2025.json", "data/sample/upstream/openmeteo_london_2025.json"]
    config = {"base_scenario":base.model_dump(), "days":args.days, "policies":POLICIES, "cases":CASES,
              "source_hashes":{k:v["sha256"] for k,v in anchors["sources"].items()},
              "execution_hashes":{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
              "training":"unchanged Jan8-Jun30", "validation":"unchanged Jul1-Aug31", "test":"all Sep1-Dec31 2025",
              "selection":"No retraining/test-best deployment selection; exploratory follow-up after prior test inspection",
              "heuristics":"same assets, EDF and battery greedy pair transfers; conservative import guard",
              "guard_comparison":{"cases":["nominal", "battery_power_20kw", "fixed_load_150pct", "fixed_load_double"],
                                  "policy":"original hybrid, carbon_weight .7, peak_weight 0", "change":"optional robust_import_cap=False versus True; unchanged physical 60-kW cap"},
              "environment":{"python":sys.version, "scipy":scipy.__version__, "numpy":np.__version__, "pandas":pd.__version__, "platform":platform.platform()}}
    (args.out/"config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    rows, compatibility, failure_dispatches, guard_rows, rejected_candidates = [], [], [], [], []
    old = pd.read_csv(ROOT/"experiments/competition_v2/daily_results.csv")
    started = time.perf_counter()
    for day_index, issue in enumerate(pd.date_range("2025-09-01", "2025-12-31", tz="UTC")[:args.days]):
        date = issue.date().isoformat()
        inputs = day_inputs(date, base, frame, by_day)
        seasonal_values = seasonal(frame.loc[frame.index < issue], issue)
        for case in CASES:
            scenario, records, realized = transformed(base, inputs, case, day_index)
            for policy in POLICIES:
                supplied = copy.deepcopy(records)
                if policy == "gridproof_seasonal":
                    for x, value in zip(supplied, seasonal_values):
                        x["ci_forecast_g_per_kwh"] = float(value)
                elif policy == "gridproof_oracle":
                    for x in supplied:
                        x["ci_forecast_g_per_kwh"] = x["ci_actual_g_per_kwh"]
                if policy.startswith("gridproof"):
                    plan, error = solve(scenario, supplied, "hybrid", .7), None
                elif policy == "immediate":
                    plan, error = solve(scenario, supplied, "immediate"), None
                else:
                    plan, error = heuristic(scenario, supplied, policy)
                row = outcome_row(date, case, policy, scenario, supplied, plan, error, realized)
                rows.append(row)
                if case == "nominal" and policy in ("immediate", "gridproof_lightgbm", "gridproof_seasonal", "gridproof_oracle"):
                    name = {"immediate":"immediate", "gridproof_lightgbm":"peak_aware_lightgbm",
                            "gridproof_seasonal":"peak_aware_seasonal", "gridproof_oracle":"peak_aware_perfect_ci_matched"}[policy]
                    previous = old[(old.date == date) & (old.policy == name)].iloc[0]
                    compatibility.append({"date":date, "policy":policy, **{k:row[k]-previous[k] for k in ["emissions_kgco2", "cost_gbp", "peak_grid_kw"]}})
                if not row["valid"] and plan and plan["dispatch"] and len(failure_dispatches) < 10:
                    failure_dispatches.append({"row":row, "dispatch":plan["dispatch"], "batch_starts":plan["batch_starts"],
                                               "planning_scenario":scenario.model_dump(), "realized_scenario":(realized or scenario).model_dump()})
        # Evidence-backed correction comparison on exactly the three legacy
        # cases with 195 rejected candidates. No weights or physical caps change.
        for case in ["nominal", "battery_power_20kw", "fixed_load_150pct", "fixed_load_double"]:
            reference = scenario_update(base, {"peak_weight":0})
            if case == "nominal":
                altered, records = reference, copy.deepcopy(inputs)
            else:
                altered, records = perturb(reference, inputs, case, day_index)
            for guarded in [False, True]:
                plan = solve(altered, records, "hybrid", .7, robust_import_cap=guarded)
                policy = "original_hybrid_guarded" if guarded else "original_hybrid_reference"
                guard_rows.append(outcome_row(date, case, policy, altered, records, plan))
                if "rejected_candidate" in plan["solver"]:
                    rejected_candidates.append({"date":date, "case":case, "policy":policy, **plan["solver"]["rejected_candidate"]})
        if (day_index+1) % 10 == 0:
            print(f"Audited {day_index+1}/{args.days} days ({len(rows)} strategy/case rows)", flush=True)
    result = pd.DataFrame(rows)
    result.to_csv(args.out/"daily_results.csv", index=False)
    pd.DataFrame(guard_rows).to_csv(args.out/"guard_before_after.csv", index=False)
    (args.out/"rejected_candidates.json").write_text(json.dumps(rejected_candidates, indent=2), encoding="utf-8")
    pd.DataFrame(compatibility).to_csv(args.out/"legacy_compatibility.csv", index=False)
    result[~result.valid].to_csv(args.out/"failures.csv", index=False)
    (args.out/"failure_dispatches.json").write_text(json.dumps(failure_dispatches, indent=2), encoding="utf-8")
    report = {"summary":summarize(result), "guard_before_after":[], "wall_seconds":time.perf_counter()-started,
              "legacy_max_abs_delta":{k:float(pd.DataFrame(compatibility)[k].abs().max()) for k in ["emissions_kgco2", "cost_gbp", "peak_grid_kw"]}}
    nominal = result[result.case == "nominal"].set_index(["date", "policy"])
    paired = nominal.xs("gridproof_lightgbm", level="policy").join(nominal.xs("gridproof_seasonal", level="policy"), rsuffix="_seasonal")
    immediate = nominal.xs("immediate", level="policy")
    increment = 100*(paired.emissions_kgco2_seasonal-paired.emissions_kgco2)/immediate.emissions_kgco2
    report["paired_ai_increment"] = {"mean_daily_percentage_points":float(increment.mean()), "block_95ci_pp":block_ci(increment),
                                     "mean_kgco2_per_day":float((paired.emissions_kgco2_seasonal-paired.emissions_kgco2).mean())}
    guard_frame = pd.DataFrame(guard_rows)
    for (case, policy), group in guard_frame.groupby(["case", "policy"]):
        report["guard_before_after"].append({"case":case, "policy":policy, "valid_days":int(group.valid.sum()),
            "fallback_days":int((group.status == "fallback_immediate").sum()),
            "rejected_candidates":int(group.candidate_rejected.sum()),
            **{f"mean_{k}":float(group.loc[group.valid, k].mean()) for k in ["emissions_kgco2", "cost_gbp", "peak_grid_kw", "delivered_workload_kwh"]}})
    (args.out/"summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"wall_seconds":report["wall_seconds"], "legacy_max_abs_delta":report["legacy_max_abs_delta"], "rows":len(result)}, indent=2))


if __name__ == "__main__":
    main()
