"""Derived report for the post-review follow-up. Reads only experiments/carpark_followup outputs.

  .venv/Scripts/python.exe scripts/report_carpark_followup.py
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/carpark_followup"
LABEL = {"edf_lightgbm_original_choice": "GridProof: LightGBM, pre-registered 20% target", "edf_lightgbm": "LightGBM, re-selected target",
         "edf_personal_quantile": "Simple personal quantile", "edf_shrinkage": "Personal shrinkage", "edf_population": "Arrival time only",
         "equal_share": "Equal share", "edf_oracle_departures": "Known departures (not deployable)", "carbon_flex": "Carbon-flex LP"}
ORDER = ["equal_share", "edf_population", "edf_personal_quantile", "edf_shrinkage", "edf_lightgbm", "edf_lightgbm_original_choice", "carbon_flex", "edf_oracle_departures"]
COLOR = {"edf_lightgbm_original_choice": "#2a78d6", "equal_share": "#eb6834", "edf_population": "#1baf7a", "edf_personal_quantile": "#eda100", "edf_oracle_departures": "#898781"}


def main():
    res = json.loads((OUT / "test_results.json").read_text())
    sel = json.loads((OUT / "selection.json").read_text())
    summary = pd.read_csv(OUT / "test_summary.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), dpi=150, sharey=True)
    for ax, regime, title in [(axes[0], "decision_time", "Decision-time inputs (post-review)"), (axes[1], "original", "Pre-registered inputs")]:
        for p, c in COLOR.items():
            g = summary[(summary.regime == regime) & (summary.policy_name == p)].sort_values("cap")
            ax.plot(g.cap, g.served_pct, color=c, lw=2, ls="--" if "oracle" in p else "-", marker="o", ms=3, label=LABEL[p])
        if regime == "decision_time":
            ceiling = 100 * (1 - res["infeasible_requests_decision_time"] / res["sessions"])
            ax.axhline(ceiling, color="#52514e", lw=1, ls=":"); ax.text(82, ceiling + .8, f"physical ceiling at 11 kW {ceiling:.1f}%", fontsize=8, color="#52514e")
        ax.set_title(title, fontsize=10, loc="left"); ax.set_xlabel("Connection limit (kW)"); ax.grid(color="#e1e0d9", lw=.8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Requests met in full (%)"); axes[0].set_ylim(50, 101)
    axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"regimes.{ext}")

    lines = ["# Post-review follow-up (exploratory)", "",
             "Protocol: [protocol.json](protocol.json). Written after two external reviews and after the 2024 test year had been examined once, so **these are exploratory checks, not independent validation**. The published results in `experiments/carpark` are unchanged.", "",
             f"{res['days']} 2024 weekdays, {res['sessions']:,} sessions. Under decision-time inputs **{res['infeasible_requests_decision_time']} requests ({100 * res['infeasible_requests_decision_time'] / res['sessions']:.1f}%) could not be met at 11 kW before the real departure by any schedule**; they stay in every denominator.", "",
             "## Selection on 2023 H2 (decision-time inputs, each family separately)", "", "| Family | Chosen | Level | Mean met in full, 100-160 kW | Mean energy short |", "|---|---|---:|---:|---:|"]
    for family, c in sel["chosen"].items():
        lines.append(f"| {family} | {c['model']} | {c['level']} | {c['selection_mean_served_pct']:.2f}% | {c['selection_mean_unserved_pct']:.2f}% |")
    lines += ["", "![Both input regimes](regimes.png)", ""]
    for regime in ("decision_time", "original", "decision_time_past_requests"):
        caps = (100, 120, 150)
        lines += [f"## {regime.replace('_', ' ')}: requests met in full", "", "| Policy | " + " | ".join(f"{c} kW" for c in caps) + " |", "|---|" + "---:|" * len(caps)]
        for p in ORDER:
            vals = [summary[(summary.regime == regime) & (summary.policy_name == p) & (summary.cap == c)] for c in caps]
            if all(v.empty for v in vals):
                continue
            cells = [f"{v.iloc[0].served_pct:.2f}% ({v.iloc[0].unserved_pct:.2f}% kWh short)" if not v.empty else "n/a" for v in vals]
            lines.append(f"| {LABEL[p]} | " + " | ".join(cells) + " |")
        lines.append("")
    lines += ["## Connection needed", "", "| Regime | Policy | >=90% | >=95% | >=98% |", "|---|---|---:|---:|---:|"]
    for regime, d in res["capacity_needed_kw"].items():
        for p, need in d.items():
            lines.append(f"| {regime} | {LABEL.get(p, p)} | {need['>=90%'] or '>200'} | {need['>=95%'] or '>200'} | {need['>=98%'] or '>200'} |")
    lines += ["", "## Paired day-level differences (A minus B), drivers with request met per day unless stated", "",
              "| Regime | Cap | A | B | Metric | Mean/day | 95% CI | Days A better | Days A worse |", "|---|---:|---|---|---|---:|---|---:|---:|"]
    for p in res["paired"]:
        lines.append(f"| {p['regime']} | {p['cap']} | {p['a']} | {p['b']} | {p['metric']} | {p['mean_diff_per_day']:+.3f} | [{p['block_ci95'][0]:+.3f}, {p['block_ci95'][1]:+.3f}] | {p['days_a_better']} | {p['days_a_worse']} |")
    lines += ["", "## Answers", "",
              "- **Q1, decision-time inputs.** The gain over equal share survives but is about half as large as in the pre-registered setup, which capped requests and set power using the real departure. GridProof (pre-registered configuration) meets +0.77, +0.88 and +0.36 more requests in full per day at 100, 120 and 150 kW; all intervals exclude zero. It also holds when the controller only knows each driver's typical past request.",
              "- **Q2, simple personal history.** Personal history is the source of the value: every personal-history estimator beats arrival-time-only by a wide margin. LightGBM is not distinguishable from the simple personal quantile at 120 or 150 kW; it is ahead of the shrinkage estimator only at the tightest cap. LightGBM remains the product model because the pre-registered and the follow-up validation selections both chose it, but the claim is now 'personal history', not 'LightGBM'.",
              "- **Carbon-flex** meets fewer requests in full than equal share under decision-time inputs at 100 and 150 kW, for about 1% lower modelled emissions at 150 kW. It is labelled experimental and not recommended.",
              "- The selection levels differ slightly between regimes (LightGBM 35% here, 20% pre-registered); the product keeps the pre-registered 20% target, whose results are reported above.",
              "", f"Wall time: {res['wall_seconds']:.0f} s."]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT / "REPORT.md")


if __name__ == "__main__":
    main()
