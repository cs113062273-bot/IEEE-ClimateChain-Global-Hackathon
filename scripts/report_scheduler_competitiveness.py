"""Recompute tables, paired smart-control differences and an exportable figure."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_scheduler_competitiveness import block_ci

OUT = ROOT / "experiments/competitiveness_audit"


def main():
    frame = pd.read_csv(OUT/"daily_results.csv")
    summary = json.loads((OUT/"summary.json").read_text())
    config = json.loads((OUT/"config.json").read_text())
    if config["days"] != 122 or frame.groupby(["case", "policy"]).size().min() != 122:
        raise ValueError("All 122 days required; partial results cannot become the final report")
    nominal = frame[frame.case == "nominal"]
    if not nominal.valid.all() or (nominal.unserved_workload_kwh > 2e-5).any():
        raise ValueError("Nominal comparison includes an invalid or incomplete strategy")
    comparisons = []
    target = nominal[nominal.policy == "gridproof_lightgbm"].set_index("date")
    for policy in ["immediate", "greedy_carbon", "greedy_cost", "peak_heuristic", "gridproof_seasonal", "gridproof_oracle"]:
        control = nominal[nominal.policy == policy].set_index("date")
        for field in ["emissions_kgco2", "cost_gbp", "peak_grid_kw"]:
            delta = target[field]-control[field]
            ci = block_ci(delta)
            comparisons.append({"control":policy, "metric":field, "paired_days":len(delta),
                                "mean_gridproof_minus_control":float(delta.mean()), "block_95ci_low":ci[0], "block_95ci_high":ci[1],
                                "gridproof_lower_days":int((delta < -1e-8).sum()), "gridproof_higher_days":int((delta > 1e-8).sum())})
    pd.DataFrame(comparisons).to_csv(OUT/"smart_baseline_comparisons.csv", index=False)
    table = pd.DataFrame(summary["summary"])
    table.to_csv(OUT/"strategy_case_summary.csv", index=False)
    guard = pd.read_csv(OUT/"guard_before_after.csv")
    before_after = []
    for case in guard.case.unique():
        before = guard[(guard.case == case)&(guard.policy == "original_hybrid_reference")].set_index("date")
        after = guard[(guard.case == case)&(guard.policy == "original_hybrid_guarded")].set_index("date")
        for field in ["emissions_kgco2", "cost_gbp", "peak_grid_kw"]:
            delta = after[field]-before[field]
            ci = block_ci(delta)
            before_after.append({"case":case, "metric":field, "mean_after_minus_before":float(delta.mean()),
                                 "block_95ci_low":ci[0], "block_95ci_high":ci[1]})
    pd.DataFrame(before_after).to_csv(OUT/"guard_paired_differences.csv", index=False)
    # Recompute headline metrics directly from the raw CSV, not printed summary.
    immediate = nominal[nominal.policy == "immediate"].set_index("date")
    headline = {"carbon_pct":float(100*(1-target.emissions_kgco2.sum()/immediate.emissions_kgco2.sum())),
                "cost_pct":float(100*(1-target.cost_gbp.sum()/immediate.cost_gbp.sum())),
                "peak_pct":float(100*(1-target.peak_grid_kw.mean()/immediate.peak_grid_kw.mean())),
                "minimum_delivered_workload_kwh":float(nominal.delivered_workload_kwh.min()),
                "maximum_delivered_workload_kwh":float(nominal.delivered_workload_kwh.max()),
                "nominal_constraint_violations":int(nominal.returned_constraint_violations.sum()),
                "nominal_deadline_violations":int(nominal.deadline_violations.sum()),
                "nominal_capacity_violations":int(nominal.capacity_violations.sum())}
    audit = {"headline_recomputed_from_dispatch_sums":headline, "legacy_max_abs_delta":summary["legacy_max_abs_delta"],
             "source_model_and_code_snapshots_still_match":all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h for p,h in config["execution_hashes"].items()),
             "rows":len(frame), "guard_rows":len(guard), "nominal_pairs":len(target),
             "limits":"Single declared simulated campus; no causal/marginal abatement; past publication availability assumed; follow-up is exploratory"}
    anchors = json.loads((ROOT/"data/trust/source_anchors.v1.json").read_text())
    audit["trained_model_matches_external_anchor"] = hashlib.sha256((ROOT/"experiments/models_portable/carbon_model.json").read_bytes()).hexdigest() == anchors["models"]["lightgbm-past-only-v1"]["sha256"]
    if not audit["source_model_and_code_snapshots_still_match"] or not audit["trained_model_matches_external_anchor"]:
        raise ValueError("Source/code changed during execution")
    (OUT/"report_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    labels = {"immediate":"Immediate", "greedy_carbon":"Greedy carbon", "greedy_cost":"Greedy cost",
              "peak_heuristic":"Peak heuristic", "gridproof_lightgbm":"GridProof LightGBM",
              "gridproof_seasonal":"GridProof Seasonal", "gridproof_oracle":"Perfect CI (reference)"}
    order = list(labels)
    means = nominal.groupby("policy").mean(numeric_only=True).loc[order]
    colors = ["#7c8795", "#63936b", "#b58a47", "#6f79a0", "#174c70", "#4c91a3", "#9e748e"]
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "axes.spines.top":False, "axes.spines.right":False})
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))
    for ax, field, title, unit in zip(axes, ["emissions_kgco2", "cost_gbp", "peak_grid_kw"],
                                    ["Modeled grid emissions exposure", "Illustrative tariff cost", "Realized daily peak import"], ["kgCO2/day", "GBP/day", "kW"]):
        ax.bar(range(len(order)), means[field], color=colors)
        ax.set_xticks(range(len(order)), [labels[x] for x in order], rotation=38, ha="right")
        ax.set_title(title)
        ax.set_ylabel(unit)
        ax.grid(axis="y", alpha=.18)
        ax.set_axisbelow(True)
    fig.suptitle("122 matched days · all strategies deliver 62 kWh/day · identical assets and limits", fontsize=13)
    fig.tight_layout(rect=[0,0,1,.93])
    fig.savefig(OUT/"strategy_comparison.png", dpi=180, bbox_inches="tight")
    fig.savefig(OUT/"strategy_comparison.svg", bbox_inches="tight")
    plt.close(fig)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
