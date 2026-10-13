# Independent benchmark consistency review

Reviewed on **2026-10-13** against the completed competition_v2 execution. This review read archived CSV/JSON and recomputed report arithmetic in memory; it did not train a model or rerun any optimization. It generated this document and the rejected-candidate listing without editing frozen inputs, CSVs, summary or solver code.

## Checks actually executed

The independent Python calculation used pandas/NumPy directly, rather than importing the benchmark summary function. It checked **112 grouped summaries** and performed **3,873 numeric comparisons**. The largest absolute floating-point discrepancy was **9.094947017729282e-13**, below the audit tolerance of 1e-8. All checks passed.

| File | Rows | Unique UTC dates | Grouped summaries checked |
|---|---:|---:|---:|
| daily_results.csv | 2,074 | 122 | 17 policies |
| tradeoff_grid.csv | 1,464 | 122 | 12 weight settings |
| sensitivities.csv | 9,760 | 122 | 16 cases x 5 policies |
| validation_diagnostics.csv | 180 | 60 | 3 weight settings |

For each nominal policy, the date list was independently compared to every date from September 1 through December 31, 2025, with no duplicates. Attempted row counts matched summary.execution.rows.

Checks included attempted days, paired days, policy/baseline failures, fallback counts, returned violation totals, wall-time mean/p95/max, CPU mean, solver-time mean, maximum retained gap, peak process RAM, carbon/cost/peak means, totals, deltas, mean/median/p10/p90 daily improvements, sample standard deviation and worsening-day counts. Rowwise carbon, cost and peak differences were independently recalculated.

Bootstrap intervals were regenerated independently for every eligible group using seed 42, 2,000 resamples, the archived group sorted by UTC date, IID resampling followed by circular seven-day blocks. Both mean-daily and aggregate IID intervals, and the mean-daily block intervals, matched the report within tolerance. This validates the stated algorithm and report arithmetic; it does not validate statistical independence, causal abatement or external generalization.

The two LightGBM-versus-seasonal paired comparisons were independently recomputed, including both confidence intervals and carbon/cost/peak mean differences: +0.201618 and +0.181878 percentage points respectively. Both seven-day block confidence intervals contain zero. The data do not demonstrate a statistically resolved carbon advantage over seasonal prediction.

## Failures retained and reporting defect disclosed

| Partition | Optimal rows | Feasible baseline rows | Infeasible rows | Rejected inputs | Immediate fallback rows |
|---|---:|---:|---:|---:|---:|
| Nominal | 1,830 | 244 | 0 | 0 | 0 |
| Tradeoff grid | 1,464 | 0 | 0 | 0 | 0 |
| Sensitivities | 6,637 | 1,708 | 610 | 610 | 195 |
| Validation diagnostics | 180 | 0 | 0 | 0 | 0 |

Sensitivity paired comparisons total 8,540 rows. The 610 impossible-deadline rows and 610 missing-forecast rows have no valid comparisons and no claimed savings. The 195 fallbacks have valid Immediate returned schedules, are kept in paired averages and must not be called optimized successes.

All 195 fallback messages explicitly say "Solver candidate failed independent constraint verification". Their grouping is:

| Sensitivity | Policy | Rejected candidate / verified fallback rows |
|---|---|---:|
| battery_power_20kw | hybrid_lightgbm | 56 |
| fixed_load_150pct | hybrid_lightgbm | 44 |
| fixed_load_double | hybrid_lightgbm | 95 |

The archived candidate_constraint_violations field is zero because it inspects the final returned fallback. It does not count discarded candidates. Consequently, zero violations means **zero reported violations on returned schedules**, not zero solver-candidate failures. The benchmark does not retain discarded residuals or their violation types/magnitudes; no such measurements are invented here.

[fallback_candidate_rejections.json](../experiments/competition_v2/fallback_candidate_rejections.json) supplies the 195 date/case/policy/message rows, source CSV hash and explicit inference limitations.

Maximum retained MIP gap is **3.314423904805593e-6**, and 48 recorded rows exceed the requested 1e-6 relative gap. Maximum recorded call wall time is **1.7530960000585765 seconds**. These are actual retained values, not a guarantee from solver settings. Fallback rows do not retain the discarded candidate gap.

## Frozen and legacy compatibility checks

The canonical configuration fingerprint matches both frozen_config.sha256 and summary.config_sha256:

**ada5e9fdfe162c75c32535a39681689df43b29b74c3952987245c3e1ae2d8de0**

This is SHA256 of sorted compact JSON, not pretty JSON file bytes. All nine execution snapshot paths were present and their byte SHA256 matched the frozen configuration at review time.

All 120 original policy/date rows were joined to the new nominal results using explicit policy-name mapping. Maximum absolute emissions delta is **0 kgCO2**; maximum absolute tariff-cost delta is **0 GBP**. The original replay_results.csv, baseline_comparison.csv, robustness.csv and benchmark_summary.json have no Git diff and match the recorded legacy hashes.

The configuration was saved before this Phase 2 run, but Phase 1 outcomes were already known. It is not immutable preregistration. The period includes September plus Q4, not Q4 alone and not four seasons. The finite grid has 12 settings, of which nine are nondominated within the grid; it is not the complete Pareto frontier.

## Figures and execution scope

All three PNG figures were visually inspected. Bars and grid points use the verified group means; daily lines use archived daily rows and preserve negative values. The grid rendering was improved after review to use grouped point numbers and a numerical legend without editing any input CSV or frozen configuration.

Native solver calls are instrumented at 10,062 and independently reconcile as 122 x 15 nominal + 122 x 10 uncached tradeoff + 122 x 14 complete/feasible sensitivity cases x 4 optimization policies + 60 x 3 validation policies. Impossible EV deadlines are rejected before the native call; missing forecasts are rejected before optimization. Total report rows are 13,478. Reused tradeoff rows retain prior timing values, so summing row times is not whole-process elapsed time. The execution report records 926.939 seconds wall, 995.984 seconds CPU, 343.289 MiB final working set and 358.699 MiB whole-process peak. RAM is process-wide and cumulative, not a per-solve allocation. The review checked CSV summary calculations, not independent OS sampling or API throughput.

This audit does not rerun source acquisition, training, physical dispatch validation, chain transactions or the full test suite; those have separate verification records.

## Archived artifact fingerprints

| Archived artifact | Byte SHA256 |
|---|---|
| summary.json | 26d32a72e310ac2f130d8fd65c4f4f89c34d4d4af565d0d282312f473070360a |
| daily_results.csv | 12777ff40f77a3b1a4e4c94cd201b584b60320733ef4f2777c15534e25be29f2 |
| tradeoff_grid.csv | 4050a35756829129f055875c4062faa6fa8ce28edc3ac87f11be7d8a3e71c616 |
| sensitivities.csv | 6b57d1221df5684846e9a342a24b487220e729bda4a6d48eef7456921405c844 |
| validation_diagnostics.csv | 5a3fb21be3aaf807375b9f7fb2e3367efcc6b85d5b07a9ccb581aa8ddd6c3d35 |
| paired_forecast_ablation.json | c8312b7eb2afa89f01de73d7a4f77f568dee62430ee4b1c64a56386da121f410 |
| frozen_config.json | 02d7c3664abda4293385c7170b14e46d540ff73c19e7dad4668f58cdaae7545d |
| frozen_config.sha256 | d77c45cac2ec749c6840ce85062573bfbef80ccc393e702903c56c1178d7f0ec |
| independent_report_audit.json | ecfbd9eb06330d37e57d9ddeb365642a7e28a574ffd6684fb72d6002a92822b1 |

The reporting script is not part of the frozen benchmark snapshot. Its current byte SHA256 after the presentation-only rendering update is:

**788251d887d8183a5164e1fbccefd649d8bbd197d3ba4b41ec5dd3d208e0f041**

The existing independent_report_audit.json contains the reporting script's narrower nominal arithmetic and legacy checks. This document records the additional independently executed cross-partition and Bootstrap audit; neither should be mistaken for a cryptographically signed external certification.
