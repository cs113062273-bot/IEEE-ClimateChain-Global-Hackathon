# Phase 2: completed 122-day competition evaluation

The full run is complete: all **122 consecutive UTC days from 2025-09-01 through 2025-12-31** were evaluated. Outputs are in [competition_v2](../experiments/competition_v2/). This September-to-December period includes September and Q4; it is not a four-season test. Original Phase 1 files and their 24-day results remain unchanged.

The fixed peak-aware engineering policy trades some modeled carbon benefit for much lower peak imports. Relative to Immediate, its **aggregate exposure improvement is 4.162%**, its **mean daily relative improvement is 4.302%**, illustrative mean tariff expense falls **7.970%**, and the ratio of mean daily peaks falls **45.624%**. This is a modeled London campus, not measured campus abatement or a carbon credit.

## Measured nominal results

All policies have 122 valid paired days, zero nominal fallback days and zero returned-schedule constraint violations. The cap policy uses an Immediate baseline with the same 40-kW guard, which is feasible on all 122 days. Workload, assets, fixed load, terminal SoC, tariff and realized outcome data are matched.

| Policy | kgCO2/day | GBP/day | Daily peak kW | Aggregate exposure improvement | Mean daily improvement | 7-day block 95% CI of mean daily improvement | Carbon-worsening days |
|---|---:|---:|---:|---:|---:|---|---:|
| Immediate | 34.945 | 61.703 | 34.053 | 0.000% | 0.000% | [0.000%, 0.000%] | 0/122 |
| Cost-first; no CI objective | 33.996 | 56.656 | 31.775 | 2.715% | 2.945% | [2.445%, 3.445%] | 10/122 |
| Carbon-first / LightGBM | 33.268 | 61.301 | 52.444 | 4.799% | 5.462% | [3.673%, 7.469%] | 21/122 |
| Original hybrid / LightGBM | 32.884 | 58.420 | 48.227 | 5.897% | 6.365% | [5.072%, 7.801%] | 7/122 |
| Perfect-CI carbon-first | 31.688 | 61.393 | 44.866 | 9.321% | 10.323% | [8.880%, 11.848%] | 0/122 |
| Hybrid / latest | 34.004 | 56.747 | 31.810 | 2.691% | 2.952% | [2.434%, 3.491%] | 10/122 |
| Hybrid / seasonal | 32.956 | 57.997 | 44.866 | 5.693% | 6.164% | [5.063%, 7.427%] | 6/122 |
| Perfect-CI matched hybrid | 31.930 | 58.352 | 44.865 | 8.627% | 9.438% | [8.124%, 10.819%] | 0/122 |
| Carbon-first / latest | 35.008 | 65.024 | 30.470 | -0.180% | -0.447% | [-1.330%, 0.385%] | 61/122 |
| Carbon-first / seasonal | 32.981 | 60.747 | 46.018 | 5.621% | 6.114% | [4.734%, 7.639%] | 8/122 |
| Peak-aware / LightGBM | 33.491 | 56.785 | 18.517 | 4.162% | 4.302% | [3.764%, 4.913%] | 4/122 |
| Peak-aware / latest | 33.860 | 56.747 | 18.409 | 3.106% | 3.347% | [2.859%, 3.839%] | 6/122 |
| Peak-aware / seasonal | 33.569 | 57.658 | 18.370 | 3.939% | 4.121% | [3.570%, 4.705%] | 6/122 |
| Perfect-CI matched peak-aware | 32.802 | 58.098 | 18.304 | 6.133% | 6.525% | [5.623%, 7.420%] | 1/122 |
| Peak-first; no forecast objective | 34.856 | 62.491 | 14.257 | 0.255% | -0.290% | [-1.397%, 0.713%] | 64/122 |
| Peak-aware / LightGBM; 40-kW cap | 33.492 | 56.785 | 18.517 | 4.158% | 4.299% | [3.762%, 4.909%] | 4/122 |
| Immediate; same 40-kW cap | 34.945 | 61.703 | 34.053 | 0.000% | 0.000% | [0.000%, 0.000%] | 0/122 |

Carbon weights are 0.7 for hybrid comparisons and 1 for carbon-first comparisons. Peak-aware hybrid adds peak weight 0.2 at a fixed 60-kW reference. Perfect-CI matched comparators use the same objective weights as their predicted counterpart. They retain calendar solar planning and outcome recourse, so they are not strict optima of realized outcomes.

The Immediate total is **4,263.275456 kgCO2**. Original LightGBM hybrid totals **4,011.885500 kgCO2**, a difference of **251.389956 kgCO2** and **5.896639%** aggregate improvement. Peak-aware LightGBM totals **4,085.857253 kgCO2**, a difference of **177.418203 kgCO2** and **4.161547%** aggregate improvement.

The original hybrid mean daily peak is **48.227 kW**, versus Immediate **34.053 kW** and peak-aware **18.517 kW**. Peak-aware cuts the original hybrid mean daily peak by **61.606%**. It gives up 1.735 percentage points of aggregate exposure improvement for this peak/cost tradeoff; it is not better on every objective.

Definitions:

~~~text
mean daily improvement = mean_d[100 * (baseline_d - policy_d) / baseline_d]
aggregate improvement = 100 * (sum_d baseline_d - sum_d policy_d) / sum_d baseline_d
ratio of mean daily peak improvement = 100 * (mean baseline_peak - mean policy_peak) / mean baseline_peak
~~~

The last definition is not the average of each day's peak percentage. CSV peak_difference_percent is positive for lower peak imports; original hybrid's mean daily peak percentage is -41.780%, while peak-aware's is +45.561%.

### Statistical uncertainty and negative days

There are 2,000 percentile Bootstrap resamples, seed 42. Reports retain IID day resampling and circular seven-day moving-block resampling. Intervals are conditional on this historical dataset and scenario; seven-day blocks do not establish generalization to other sites or seasons.

| Policy | IID 95% CI, mean daily improvement | IID 95% CI, aggregate improvement | Seven-day block 95% CI, mean daily improvement |
|---|---|---|---|
| Original hybrid / LightGBM | [5.535%, 7.190%] | [5.062%, 6.737%] | [5.072%, 7.801%] |
| Peak-aware / LightGBM | [3.845%, 4.752%] | [3.710%, 4.613%] | [3.764%, 4.913%] |
| Peak-first; no forecast objective | [-1.045%, 0.447%] | [-0.397%, 0.873%] | [-1.397%, 0.713%] |

Peak-aware LightGBM has four carbon-worsening days, preserved in daily_results.csv:

| UTC date | Daily exposure improvement |
|---|---:|
| 2025-09-06 | -4.536% |
| 2025-09-15 | -0.475% |
| 2025-10-04 | -0.447% |
| 2025-10-13 | -0.031% |

It has zero cost-worsening and zero peak-worsening nominal days. Original hybrid has seven carbon-worsening days and 108 peak-worsening days. The no-forecast peak-first control lowers mean peak to 14.257 kW, but worsens carbon on 64 days and illustrative tariff expense on all 122 days. It is a useful control, not an AI or universal climate-benefit claim.

### AI contribution: no demonstrated material advantage over seasonal prediction

[paired_forecast_ablation.json](../experiments/competition_v2/paired_forecast_ablation.json) compares each model and seasonal policy on the exact same days and objective weights.

| Matched comparison, LightGBM minus seasonal | Mean daily improvement difference, percentage points | Seven-day block 95% CI, percentage points | Mean kgCO2/day difference | Mean GBP/day difference | Mean peak kW difference |
|---|---:|---|---:|---:|---:|
| Original hybrid | +0.201618 | [-0.406593, +0.746872] | -0.071257 | +0.422881 | +3.361497 |
| Peak-aware hybrid | +0.181878 | [-0.187892, +0.557264] | -0.077918 | -0.872901 | +0.146826 |

Both IID intervals also contain zero. The full-period means favor LightGBM slightly, but these experiments **do not demonstrate a material, statistically resolved carbon advantage over a simple seasonal forecast**. The earlier 24-day result favored seasonal mean daily improvement slightly; both results remain visible. Prediction accuracy and decision value are separate metrics. No model retraining or test-best policy selection was performed for this run.

## Peak-aware mathematical change

The original normalized carbon/cost objective is preserved and gains a disclosed epigraph term:

~~~text
J = carbon_weight * predicted_kgCO2 / 50
  + (1 - carbon_weight) * illustrative_GBP / 100
  + peak_weight * z / 60
  + 1e-7 * total_battery_throughput_kWh

z >= (fixed_kWh + EV_kWh + batch_kWh + charge_kWh - discharge_kWh) / 0.5h
z <= peak_cap_kw, when a hard cap is requested
~~~

The default **zero-PV guard** bounds net demand before solar credit. Nonnegative realized PV cannot increase imports above that envelope. This protects the peak bound without using future weather. Independent checks enforce the envelope and realized grid cap. Optional forecast-import peak mode may fail a replay cap and must not be counted as a feasible success.

Battery SoC, efficiencies, power limits, initial/terminal balance, EV deadlines/shared charger capacity and contiguous batch limits remain in the MILP. Default peak_weight=0 preserves original policy behavior.

The peak-first control uses zero decision PV and minimizes net-demand peak without carbon or tariff terms. CI, solar and tariff forecast changes do not alter its decisions. Historical CI and radiation-derived solar enter only its realized scoring. The input contract still requires a complete CI forecast, even for controls whose objective does not use it; missing CI is reported as rejected, not silently imputed.

## Carbon-cost-peak exploratory grid

The fixed grid has **12 settings**: carbon weights 0, 0.35, 0.7, 1 crossed with peak weights 0, 0.2, 0.5. It produces 1,464 paired rows. Weight 0.2 is an engineering setting, not a test-selected winner. The grid is an exploratory comparison, **not a complete Pareto frontier**. Nine points are nondominated within this finite sampled grid.

| Carbon weight | Peak weight | kgCO2/day | GBP/day | Daily peak kW |
|---:|---:|---:|---:|---:|
| 0 | 0 | 33.996 | 56.656 | 31.775 |
| 0 | 0.2 | 33.879 | 56.655 | 18.491 |
| 0 | 0.5 | 33.864 | 56.655 | 18.551 |
| 0.35 | 0 | 33.175 | 56.816 | 37.056 |
| 0.35 | 0.2 | 33.592 | 56.656 | 18.168 |
| 0.35 | 0.5 | 33.593 | 56.670 | 18.171 |
| 0.7 | 0 | 32.884 | 58.420 | 48.227 |
| 0.7 | 0.2 | 33.491 | 56.785 | 18.517 |
| 0.7 | 0.5 | 33.785 | 58.423 | 17.002 |
| 1 | 0 | 33.268 | 61.301 | 52.444 |
| 1 | 0.2 | 33.314 | 58.848 | 20.125 |
| 1 | 0.5 | 33.979 | 60.987 | 16.035 |

Figures were inspected and checked against CSV-derived means. The grid figure now uses numbered groups and a numerical legend to distinguish clustered points. Unfavorable days remain visible.

- [Carbon / cost / peak comparison](../experiments/competition_v2/figures/carbon_cost_peak.png)
- [All 122 daily tradeoffs](../experiments/competition_v2/figures/daily_tradeoffs.png)
- [Fixed exploratory weight grid](../experiments/competition_v2/figures/weight_tradeoff_grid.png)

PNG and SVG are available for all three.

## Sensitivities, failed inputs and rejected candidates

There are 16 sensitivity cases, each with 122 days and five matched policies: Immediate, cost-first, original hybrid, peak-aware hybrid and peak-first. Changes are explicit experiment transforms, not changes to the production site's source weather/load/tariff. The following table reports peak-aware LightGBM; the complete 9,760-row CSV includes every policy and failure.

| Sensitivity | Valid pairs | Aggregate exposure improvement | Mean daily improvement | Daily peak kW | Carbon-worsening days |
|---|---:|---:|---:|---:|---:|
| battery_0kwh | 122/122 | 0.722% | 0.661% | 18.318 | 44/122 |
| battery_20kwh | 122/122 | 2.502% | 2.551% | 18.494 | 6/122 |
| battery_80kwh | 122/122 | 5.500% | 5.579% | 18.370 | 8/122 |
| battery_power_5kw | 122/122 | 3.254% | 3.283% | 18.466 | 8/122 |
| battery_power_20kw | 122/122 | 4.229% | 4.369% | 19.373 | 4/122 |
| fixed_load_half | 122/122 | 6.573% | 6.849% | 12.505 | 4/122 |
| fixed_load_150pct | 122/122 | 2.877% | 2.945% | 25.154 | 6/122 |
| fixed_load_double | 122/122 | 2.206% | 2.242% | 31.821 | 7/122 |
| ev_deadline_tighter | 122/122 | 4.020% | 4.115% | 19.121 | 6/122 |
| ev_deadline_infeasible | 0/122 | No valid comparison | No valid comparison | Unavailable | Not applicable |
| forecast_bias_plus30 | 122/122 | 4.439% | 4.552% | 19.070 | 3/122 |
| forecast_noise_30g | 122/122 | 2.548% | 2.668% | 21.456 | 20/122 |
| forecast_timing_inverted | 122/122 | 2.776% | 2.746% | 18.671 | 24/122 |
| solar_20pct | 122/122 | 3.907% | 3.998% | 19.181 | 4/122 |
| efficiency_85pct | 122/122 | 1.757% | 1.720% | 18.415 | 19/122 |
| missing_forecast_rejected | 0/122 | No valid comparison | No valid comparison | Unavailable | Not applicable |

**Failures and fallbacks remain part of the results:**

- Impossible four-slot EV windows: 610 infeasible rows, including all matched baselines; zero favorable comparisons claimed.
- One missing CI decision record: 610 input-rejected rows, including controls; zero favorable comparisons claimed.
- The remaining 8,540 sensitivity rows have valid paired returned schedules, including 195 Immediate fallbacks.
- All 195 fallback messages state "Solver candidate failed independent constraint verification". They occur in original hybrid: 56/122 days at 20-kW battery power, 44/122 days at 1.5x fixed load, and 95/122 days at 2x fixed load.
- Thus **at least 195 solver candidates were rejected**. The fallback mechanism returns a physically verified Immediate schedule and includes its zero-improvement result in paired averages; these are not successful optimized solutions.
- The CSV field candidate_constraint_violations is zero because it counts violations on the returned schedule. It does **not** preserve discarded candidate residuals. It must not be cited as proof that every solver candidate passed.
- Candidate violation types/magnitudes and discarded candidate MIP gaps were not retained. [Derived rejected-candidate listing](../experiments/competition_v2/fallback_candidate_rejections.json) classifies the 195 rows from their messages only; it does not invent residual measurements.

Forecast noise and inverted timing lower peak-aware benefit and increase negative days. With no battery, aggregate improvement falls to 0.722% and 44/122 days worsen. These results limit generalization; they are not hidden by the nominal mean.

## Execution measurements

[environment.json](../experiments/competition_v2/environment.json) records Windows 11, Intel i7-12700H (14 cores / 20 logical processors), approximately 15.7 GiB visible RAM, one benchmark worker and one native solver thread.

| Measurement | Result |
|---|---:|
| Whole benchmark wall time | 926.939 seconds |
| Whole process CPU time | 995.984 seconds |
| Instrumented native MILP calls | 10,062 |
| Nominal / tradeoff / sensitivity / validation rows | 2,074 / 1,464 / 9,760 / 180 |
| Peak-aware nominal mean / p95 / max call wall time | 0.070452 / 0.272744 / 0.535329 seconds |
| All recorded rows mean / p95 call wall time | 0.068003 / 0.299738 seconds |
| Maximum recorded call wall time | 1.753096 seconds |
| Maximum recorded solver time | 1.750368 seconds |
| Maximum retained MIP gap | 0.000003314424 |
| Rows with retained gap above requested 0.000001 | 48 |
| Final process working set | 343.289 MiB |
| Whole-process peak working set | 358.699 MiB |

The maximum call is peak-aware LightGBM with 30-g/kWh forecast noise on 2025-09-27. The maximum retained gap is original hybrid with half fixed load on 2025-12-11. The solver requests 1e-6 relative gap but this is **not a guaranteed upper bound on all returned gaps**; the measured maximum is reported, not rounded down to the target.

Some tradeoff rows reuse already solved matching nominal policies, so row counts, summed row timings and native-call counts are different quantities. Whole-process wall time includes data loading, validation diagnostics and reporting. CPU time can exceed elapsed time due to process threads. RAM includes Python, native libraries, models, cached data and report construction; cumulative row process peaks are not isolated memory per solve. These measurements are not a public API throughput benchmark.

## Frozen boundary, compatibility and reproducibility

Training remains 2025-01-08 through 06-30; validation 07-01 through 08-31; testing 09-01 through 12-31. Validation diagnostics use the frozen June-trained candidate, not a historically unavailable validation-selected model. There are 60 complete validation days; 2025-08-10 and 08-11 lack complete actual outcomes and are explicitly listed in validation_coverage.json.

frozen_config.json and its execution snapshots were recorded before this run. Its SHA256 is the sorted compact JSON fingerprint **ada5e9fdfe162c75c32535a39681689df43b29b74c3952987245c3e1ae2d8de0**, not the hash of pretty-printed file bytes. All nine listed snapshots matched during independent report review.

This is **not immutable preregistration**: Phase 1 test outcomes had already been examined before Phase 2 design. No training/parameter tuning or automatic test-best deployment selection is performed by the benchmark. The test weight grid is exploratory and clearly labeled.

Portable LightGBM predictions differ from the saved Phase 1 series by at most **2.84217e-14 gCO2/kWh**. All original 120 policy/date emissions and cost values match exactly; maximum absolute delta is **0**. The four original experiment files remain Git-unchanged. [Independent consistency review](BENCHMARK_CONSISTENCY.md) records the complete reporting audit.

Reproduction commands:

~~~powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_peak.py -q
.\.venv\Scripts\python.exe scripts/run_competition_benchmark.py
.\.venv\Scripts\python.exe scripts/report_competition_benchmark.py
~~~

The run command intentionally overwrites competition_v2 and makes a new execution fingerprint/timing record. Copy archived outputs first if preserving this exact execution. Do not call it a byte-for-byte reproduction of timing or regenerated evidence.

Limitations remain: national average CI, synthetic campus demand/EV/battery, simplified PV conversion, illustrative tariffs, assumed publication availability/no historical revision archive, independent daily terminal reset, no continuous multi-day dispatch, no field measurements, no causal marginal avoided-emissions claim and no guarantee of source-provider truth.
