"""Derived report for the car-park evaluation. Reads only experiments/carpark outputs.

  .venv/Scripts/python.exe scripts/report_carpark.py
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/carpark"
LABEL = {"gridproof_priority": "GridProof priority (personal departure model)", "equal_share": "Equal-share load balancing",
         "priority_population_model": "Same priority rule, population model", "priority_oracle_departures": "Priority with true departures (not deployable)",
         "gridproof_carbon_flex": "GridProof carbon-flex LP", "carbon_flex_oracle_departures": "Carbon-flex LP with true departures (not deployable)",
         "uncontrolled": "Uncontrolled, ignores the cap (reference)"}
COLOR = {"gridproof_priority": "#2a78d6", "equal_share": "#eb6834", "priority_population_model": "#1baf7a", "priority_oracle_departures": "#898781"}


def main():
    result = json.loads((OUT / "test_results.json").read_text())
    daily = pd.read_csv(OUT / "test_daily.csv")
    summary = pd.read_csv(OUT / "test_summary.csv")
    sel = json.loads((OUT / "selection.json").read_text())
    agg = daily.groupby(["policy_name", "cap"]).agg(delivered=("delivered_kwh", "sum"), co2=("emissions_kgco2", "sum")).reset_index()
    agg["g_per_kwh_delivered"] = 1000 * agg.co2 / agg.delivered
    summary = summary.merge(agg[["policy_name", "cap", "g_per_kwh_delivered"]], on=["policy_name", "cap"])

    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=150)
    for p, c in COLOR.items():
        g = summary[summary.policy_name == p].sort_values("cap")
        ax.plot(g.cap, g.served_pct, color=c, lw=2, ls="--" if "oracle" in p else "-", marker="o", ms=3, label=LABEL[p])
    ax.set_xlabel("Connection limit (kW)"); ax.set_ylabel("Drivers whose request was met in full (%)")
    ax.set_ylim(50, 100.5); ax.grid(color="#e1e0d9", lw=.8); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"Held-out 2024: {result['days']} weekdays, {result['sessions']:,} real sessions", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"hosting_curve.{ext}")

    def row(p, cap):
        return summary[(summary.policy_name == p) & (summary.cap == cap)].iloc[0]

    lines = ["# Car-park departure-risk evaluation (derived)", "",
             f"Protocol: [protocol.json](protocol.json). Selection on {sel['selection_days']} days of 2023 H2 ({sel['selection_window'][0]} to {sel['selection_window'][1]}); "
             f"test on {result['days']} weekday site days of 2024 with {result['sessions']:,} real sessions, run once with the frozen selection. "
             "Session behaviour is real (Utrecht office car park, rails E+M); the grid day is the same-weekday 2025 GB day; building load and tariff are synthetic; chargers are simulated.", "",
             f"Selected service policy: **{sel['service_policy']['policy'].upper()} with the personal LightGBM departure model, ready-by target at the {sel['service_policy']['level']:.0%} departure quantile**. "
             f"Selected carbon-flex LP: risk penalty {sel['carbon_flex']['risk_penalty']}, hard promise {sel['carbon_flex']['hard_promise_level']}.", "",
             "## Connection needed for a service level", "", "| Policy | >=95% requests met in full | >=98% | >=99% |", "|---|---:|---:|---:|"]
    for p, need in result["capacity_needed_kw"].items():
        lines.append(f"| {LABEL[p]} | {need['>=95%'] or '>200 / n.a.'} | {need['>=98%'] or '>200 / n.a.'} | {need['>=99%'] or '>200 / n.a.'} |")
    lines += ["", "LP policies were run only at 100, 120 and 150 kW; their 'n.a.' entries mean not reached at those caps. Uncontrolled charging always serves everyone because it ignores the limit.", "",
              "![Hosting curve](hosting_curve.png)", ""]
    for cap in (100, 120, 150):
        lines += [f"## {cap} kW connection", "", "| Policy | Requests met in full | Energy short | kgCO2/day | g/kWh delivered (site) | GBP/day | Mean peak kW | Slots over cap |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for p in ["equal_share", "gridproof_priority", "priority_population_model", "gridproof_carbon_flex", "priority_oracle_departures", "carbon_flex_oracle_departures", "uncontrolled"]:
            r = summary[(summary.policy_name == p) & (summary.cap == cap)]
            if r.empty:
                continue
            r = r.iloc[0]
            lines.append(f"| {LABEL[p]} | {r.served_pct:.2f}% | {r.unserved_pct:.2f}% | {r.emissions_kgco2_per_day:.2f} | {r.g_per_kwh_delivered:.1f} | {r.cost_gbp_per_day:.2f} | {r.peak_import_kw_per_day:.1f} | {int(r.cap_exceeded_slots)} |")
        lines.append("")
    lines += ["## Paired day-level differences (A minus B)", "", "Moving-block bootstrap, blocks of 5 site days, 2,000 resamples. Exploratory; no multiple-comparison correction.", "",
              "| Cap | A | B | Metric | Mean/day | 95% CI | Days A better | Days A worse |", "|---:|---|---|---|---:|---|---:|---:|"]
    for p in result["paired"]:
        lines.append(f"| {p['cap']} | {p['a']} | {p['b']} | {p['metric']} | {p['mean_diff_per_day']:+.3f} | [{p['block_ci95'][0]:+.3f}, {p['block_ci95'][1]:+.3f}] | {p['days_a_better']} | {p['days_a_worse']} |")
    worse = []
    for cap in (100, 120, 150):
        a = daily[(daily.cap == cap) & (daily.policy_name == "gridproof_priority")].set_index("day")
        b = daily[(daily.cap == cap) & (daily.policy_name == "equal_share")].set_index("day")
        diff = (a.served - b.served)
        for d in diff[diff < 0].index:
            worse.append(f"| {cap} | {d} | {int(a.loc[d, 'served'])}/{int(a.loc[d, 'sessions'])} | {int(b.loc[d, 'served'])}/{int(b.loc[d, 'sessions'])} | {a.loc[d, 'unserved_kwh']:.2f} | {b.loc[d, 'unserved_kwh']:.2f} |")
    lines += ["", "## Days where GridProof priority met fewer requests in full than equal share", "",
              "| Cap | Day | GridProof | Equal share | GridProof kWh short | Equal share kWh short |", "|---:|---|---:|---:|---:|---:|"] + worse
    cov = result["departure_coverage_test"]
    lines += ["", "## Departure-model calibration on 2024 (share leaving before each predicted quantile)", "",
              "| Level | Personal model, site | Personal model, all rails | Population model, site |", "|---:|---:|---:|---:|"]
    for level in cov["lightgbm"]["site"]:
        lines.append(f"| {level} | {cov['lightgbm']['site'][level]:.3f} | {cov['lightgbm']['all_rails'][level]:.3f} | {cov['population']['site'][level]:.3f} |")
    sens_path = OUT / "sensitivity.csv"
    if sens_path.exists():
        sens = pd.read_csv(sens_path)
        lines += ["", "## Sensitivity of the frozen policies (share of requests met in full)", "",
                  "From `scripts/sensitivity_carpark.py`; one assumption changed at a time for every policy; nothing re-selected.", "",
                  "| Case | Cap kW | Equal share | GridProof priority | Priority, population model |", "|---|---:|---:|---:|---:|"]
        for (case, cap), g in sens.groupby(["case", "cap"]):
            v = g.set_index("policy_name").served_pct
            lines.append(f"| {case} | {cap} | {v['equal_share']:.2f}% | {v['gridproof_priority']:.2f}% | {v['priority_population_model']:.2f}% |")
        lines += ["", "With requests unknown, priority does slightly better than nominal at tight caps: the nominal tie-break (largest remaining request first) "
                  "is probably not ideal. Observed on the test year, so it is reported and not tuned."]
    lines += ["", "## Reading these results honestly", "",
              "- The service gain comes from ordering: with a cap, someone must wait, and knowing who is likely to leave first decides who that is. Equal share and the population model order badly.",
              "- Modelled emissions rise with GridProof priority because more energy is delivered; per delivered kWh the site intensity is essentially unchanged. This is not a carbon-reduction result.",
              "- Carbon-flex is roughly as good as equal share on service at 150 kW and lowers modelled emissions about 1%, at higher illustrative cost and noticeably worse service than priority. Early-departure risk limits load shifting at a workplace.",
              "- The LP is myopic about arrivals it cannot foresee. It shifts current cars into later, cleaner or flatter hours; under a hard cap, morning capacity left idle is lost, and later arrivals find the afternoon committed. Even with true departures it meets only "
              f"{row('carbon_flex_oracle_departures', 100).served_pct:.1f}% at 100 kW versus {row('priority_oracle_departures', 100).served_pct:.1f}% of requests in full for greedy priority. An arrival forecast would be needed before load shifting can be recommended at tight caps; this was found on the test year and is reported, not tuned away.",
              "- The oracle rows show the value of better departure information (for example drivers confirming their departure). They are not achievable by the model alone.",
              f"- Excluded test days and reasons: {', '.join(f'{d} ({r})' for d, r in result['excluded_days'])}.",
              "- One site, one population, Dutch behaviour on GB grid days, 11 kW per car unless a session shows more, requests assumed known at plug-in, whole half-hour presence, no stationary battery, simulated chargers.",
              "", f"Wall time of the test stage: {result['wall_seconds']:.0f} s. Environment: Python {result['environment']['python']}."]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT / "REPORT.md")


if __name__ == "__main__":
    main()
