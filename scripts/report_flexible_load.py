"""Report for the stage-1 flexible-load direction experiment. Reads experiments/flexible_load outputs only.

  .venv/Scripts/python.exe scripts/report_flexible_load.py
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/flexible_load"
NAMES = {"fixed_time_of_day": "Fixed time-of-day rule", "seasonal_median": "Seasonal median (7 days)", "persistence_blend": "Persistence blend",
         "lightgbm_multi_horizon": "Multi-horizon LightGBM", "perfect_foresight": "Perfect foresight, same rules",
         "neso_published_reference": "NESO published forecast (reference only)"}


def main():
    r = pd.read_csv(OUT / "results.csv"); s = json.loads((OUT / "summary.json").read_text())
    acc = pd.read_csv(OUT / "forecast_accuracy.csv"); b = pd.read_csv(OUT / "breakdown_24h.csv")
    L = ["# Stage 1: carbon value of delaying flexible batch electricity", "",
         "Protocol: [protocol.json](protocol.json), written before results. Jobs: 12 per day arriving 08:00-19:30 UTC, 1-4 h, 5-20 kW, contiguous, sharing an 80 kW limit; "
         f"about {s['flexible_energy_kwh_per_day']:.0f} kWh of flexible work per day. The same jobs run under every policy; reductions compare against running as soon as capacity allows with the same deadline. "
         "Decisions use only carbon observed before the job arrives and commit at arrival. Location-based average GB intensity: exposure, not causal marginal abatement.", "",
         f"Selection on validation (May-Jun 2025, carbon at 24 h): persistence tau {s['selection']['chosen_tau_hours']} h, LightGBM '{s['selection']['chosen_lightgbm']}'. "
         "Independent test: 2026-01-01 to 2026-10-16 NESO actual data, downloaded after the design and never used for any choice. Exploratory test: Jul-Dec 2025, months examined in earlier work.", ""]
    for period, title in (("independent_test", "Independent test, 2026"), ("exploratory_test", "Exploratory test, Jul-Dec 2025")):
        t = r[r.period == period]
        L += [f"## {title}: carbon exposure reduction versus immediate", "", "| Policy | 3 h | 8 h | 24 h | 48 h |", "|---|---:|---:|---:|---:|"]
        for p, name in NAMES.items():
            cells = []
            for w in (3, 8, 24, 48):
                x = t[(t.policy == p) & (t.flex_h == w)].iloc[0]; ci = json.loads(x.reduction_ci95)
                cells.append(f"{x.reduction_pct:.1f}% [{ci[0]:.1f}, {ci[1]:.1f}]")
            L.append(f"| {name} | " + " | ".join(cells) + " |")
        L += ["", "| At 24 h | Missed deadlines | Cost change | Worse days | Mean delay h | Mean daily peak kW (immediate {:.1f}) | Share of perfect foresight |".format(
            t[(t.policy == "immediate") & (t.flex_h == 24)].iloc[0].peak_kw_mean_daily), "|---|---:|---:|---:|---:|---:|---:|"]
        for p, name in NAMES.items():
            x = t[(t.policy == p) & (t.flex_h == 24)].iloc[0]
            L.append(f"| {name} | {x.missed} | {x.cost_change_pct:+.1f}% | {x.worse_days}/{x.days} | {x.mean_delay_h:.1f} | {x.peak_kw_mean_daily:.1f} | {x.share_of_perfect_foresight:.2f} |")
        imm = t[(t.policy == "immediate") & (t.flex_h == 24)].iloc[0]; sm = t[(t.policy == "seasonal_median") & (t.flex_h == 24)].iloc[0]
        L += ["", f"Scale: {imm.energy_kwh / imm.days:.0f} kWh/day of flexible work at {1000 * imm.kgco2 / imm.energy_kwh:.0f} g/kWh when run immediately. "
              f"The seasonal median at 24 h avoids {(imm.kgco2 - sm.kgco2) / imm.days:.1f} kg/day, {365 * (imm.kgco2 - sm.kgco2) / imm.days / 1000:.1f} t/yr, "
              f"{1000 * (imm.kgco2 - sm.kgco2) / sm.energy_kwh:.0f} g per flexible kWh.", ""]
    L += ["## Where the value is (24 h, 2026)", "", "| Group | Fixed rule | Seasonal median | LightGBM | Perfect foresight |", "|---|---:|---:|---:|---:|"]
    bb = b[b.period == "independent_test"].pivot_table(index=["group", "value"], columns="policy", values="reduction_pct")
    for (g, v), row in bb.iterrows():
        L.append(f"| {g}: {v} | {row.fixed_time_of_day:.1f}% | {row.seasonal_median:.1f}% | {row.lightgbm_multi_horizon:.1f}% | {row.perfect_foresight:.1f}% |")
    L += ["", "## Forecast error (MAE g/kWh, 2026)", "", "| Method | 0-6 h | 6-24 h | 24-52 h |", "|---|---:|---:|---:|"]
    for x in acc[acc.period == "independent_test"].itertuples():
        L.append(f"| {NAMES.get(x.method, x.method)} | {x._3:.1f} | {x._4:.1f} | {x._5:.1f} |")
    L += ["", "The NESO published field has nearly constant ~10 g/kWh error at every lead time, consistent with a short-lead forecast whose issue time is not archived. It is not a valid decision baseline.",
          "", "## Reading", "",
          "- Waiting matters, and the length of the wait sets the value: about 6% at 3 h, 12% at 8 h and 26-27% at 24 h on the unseen 2026 period with simple forecasts, with no missed deadlines.",
          "- Roughly half of the 24 h value needs live grid information: a fixed clock rule gets 12.9%; a 7-day seasonal median gets 25.9%. LightGBM and persistence add about 1.5 points beyond that; the ML model is not the source of the value.",
          "- Beyond 24 h the forecasts stop improving (48 h is close to 24 h), although perfect foresight keeps gaining. The forecast horizon, not the flexibility, becomes the limit.",
          "- Jobs that arrive in the evening carry most of the value; morning arrivals gain least, and a fixed clock rule makes them worse.",
          "- Costs: the illustrative tariff falls with carbon here because night is cheap in that synthetic tariff. Typical daily peaks of the flexible load rise about 25-30% as jobs bunch into clean hours, always within the 80 kW limit. 15-20% of days are worse than running immediately.",
          "- Limits: synthetic workload (real campus job traces not yet used), commit at arrival without re-planning, no battery or PV, national average intensity.",
          "", f"Wall time {s['wall_seconds']:.0f} s. Data: {s['data']['slots']} half-hours, {s['data']['missing_actual_slots']} missing actual values interpolated for scoring only."]
    (OUT / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT / "REPORT.md")


if __name__ == "__main__":
    main()
