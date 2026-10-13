# Executed evaluation

These measurements come from running the checked-in Python scripts on authentic 2025 national GB carbon records. They describe simulated campus outcomes, not a field trial or certified carbon abatement. Files under `experiments/` contain the actual interval/day outputs and summary reports.

## Forecast experiment

The raw 2025 CI series has 17,520 half-hour records with 43 null actuals. Null actuals are never replaced with forecasts. Training uses 172 complete days (8,256 intervals), January 8–June 30. Validation uses 60 complete July–August days; the locked September–December test contains 122 days (5,856 intervals). The frozen model is evaluated at each rolling midnight issue, with all lag lookups strictly earlier than issue time. No shuffled folds, observed future weather/demand, test-period tuning or unverifiable historical forecast issuance is used in primary predictions.

LightGBM 4.6.0 uses 180 trees, 15 leaves, max depth 5, learning rate 0.04, min child 60, seed 42, one thread. Calendar features, latest CI, past 24 h/7 day means and same-slot lags 1–7 days are available at midnight. The choice between LightGBM and seven-day seasonal median was fixed by validation MAE; LightGBM won 26.269 vs 34.590 gCO2/kWh. This validation choice remained locked for test. Rows with unavailable actual outcomes are skipped as whole days and counted explicitly.

| Method | Locked-test MAE gCO2/kWh | RMSE gCO2/kWh | Information |
|---|---:|---:|---|
| Latest known value | 34.836 | 49.794 | Past-only |
| Same slot previous day | 40.996 | 53.295 | Past-only |
| Seven-day seasonal median | 47.060 | 60.193 | Past-only |
| LightGBM | 36.982 | 47.447 | Past-only; validation-selected |
| NESO historical published forecast | 9.233 | 12.845 | Secondary; issuance unverified |

**The custom model does not beat latest-known test MAE and does not beat NESO's retrospective forecast.** It improves RMSE over the past-only baselines but no state-of-the-art claim is justified. Forecast uncertainty is uncalibrated; the UI displays no invented confidence band. Solar uses a physical calendar forecast; synthetic fixed load follows a known declared profile. There is no independent site solar/load forecasting accuracy claim.

## Scheduling experiment

The locked scheduling sample contains 24 equally spaced UTC dates selected from September 1–December 31 before solving. Every policy receives the same 20-kWp rooftop, 40-kWh battery, 62-kWh flexible workload, 232-kWh fixed load, EV windows, shared charger, contiguous batch, illustrative tariff and import cap. MILP optimizes with past-only CI and calendar solar. Observed CI and radiation-derived simulated solar enter only outcome scoring with fixed decisions and grid/curtailment recourse. Initial and terminal battery SoC match. See `ASSUMPTIONS.md` for full parameters.

Positive difference means lower modeled emissions exposure than immediate. The table averages per-day percentages; it is not the percentage of aggregate physical abatement. Cost deltas are illustrative GBP/day, not bills.

| Policy | Mean difference % | Median % | p10/p90 % | Day bootstrap 95% CI % | Mean cost delta GBP | Non-improving days | Constraint violations |
|---|---:|---:|---|---|---:|---:|---:|
| Immediate, battery idle | 0 | 0 | 0 /0 | 0 /0 | 0 | 24/24 | 0 |
| Cost-first | 3.256 | 3.733 | 0.806 /5.684 | 2.264 /4.167 | −5.046 | 2/24 | 0 |
| Carbon-first | 6.821 | 5.616 | −1.049 /18.297 | 4.086 /9.460 | −0.154 | 6/24 | 0 |
| Hybrid, weight 0.7 | 7.358 | 5.847 | 2.705 /14.932 | 5.416 /9.417 | −3.369 | 1/24 | 0 |
| Perfect-carbon oracle | 11.414 | 9.406 | 5.230 /19.270 | 9.091 /13.922 | −0.067 | 0/24 | 0 |

Bootstrap uses 2,000 resampled **days**, seed 42. Intervals are not treated as independent observations. On the measured host the hybrid solver averaged 0.041 seconds and maximized 0.103 seconds in the latest run; cold import/startup time is excluded. Solver timings vary by machine and load. Carbon oracle sees perfect future actual CI, while solar remains the forecast, so its result is an unrealistic information comparator rather than a proven optimum of realized outcomes.

A concrete failure: October 13, 2025 hybrid increases modeled exposure from 74.144376 to 74.799573 kgCO2 (−0.884% difference), while lowering illustrative cost by£1.470. The solver remains feasible and completes the identical workload. Such non-improvement is preserved in reports instead of selecting only favorable examples.

Robustness tests run each of the 24 days with+30% CI forecast bias, inverted forecast timing, battery one-way efficiencies 0.85, solar forecast and outcome scaled to 20%, and a missing CI decision input. The first four complete and include 24 combined non-improving cases; all 24 missing-input cases reject explicitly. `robustness.csv` records every case and status. These are sensitivities, not probabilistic uncertainty calibration. January 15 and August 12 are separately sourced offline demo windows and are not counted as locked test scheduling days.

## Verification and reproducibility

Backend tests exercise energy conservation, exact EV energy/deadlines/shared cap, batch contiguity/concurrency, SoC bounds and matching endpoints, battery modes, PV curtailment, nonnegative imports, infeasible requests, missing/null/out-of-order/DST-offset inputs, forecast information leakage, solver outage/timeout fallback, API masking, canonical digest, tampered metrics and freshly rehashed invalid/nonfinite claims. The standalone `scripts/verify_evidence.py` imports no backend implementation and independently reconstructs SHA 256, physical constraints, workloads and metric sums. Provider snapshots retain source IDs, raw digests, retrieval UTC, licence and attribution; source code hashes are separate. Mutable QA manifest timestamps are excluded from evidence artifact hashes.

The canonical encoder is explicitly `gridproof-canonical-json-v1`: compact UTF-8 JSON, ASCII keys sorted recursively, finite floats converted to fixed nine-place decimal strings, negative zero normalized, integers restricted to JavaScript's safe range. This is not presented as RFC 8785. Browser and Node independently reproduce the evidence fingerprint. Hash and arithmetic verification certify integrity and model consistency only.

Run on Windows from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/train_models.py
.\.venv\Scripts\python.exe scripts/run_benchmark.py --days 24
.\.venv\Scripts\python.exe scripts/make_demo_fixture.py
.\.venv\Scripts\python.exe scripts/smoke_test.py
.\.venv\Scripts\python.exe scripts/verify_evidence.py data/sample/evidence.json
```

Bulk acquisition is required to rerun full-year training/held-out benchmarks. The distributed sample includes genuine source records and seven prior days for each demo window; it supports offline seasonal forecasts and constraint verification without bulk data or network. The trusted locally generated model pickle is ignored by version control and never accepted as an uploaded artifact. If no trained model is present, the backend labels its seasonal fallback explicitly; the sample alone does not pretend to reproduce the full-year ML experiment. Remaining limitations are one year, one site template, sampled test scheduling days, average national rather than marginal/regional intensity, unverified historic forecast issuance, PV simplifications and simulated facility/tariff.

The validation-selected artifact is usable from September 1. Applying that selection during July or August would use information from later validation outcomes, so those earlier replay dates explicitly use seasonal median instead. Past observed timestamps are assumed to be available at the midnight decision; historical publication latency is not archived.

Repeated API replay tests exposed a native Windows HiGHS access violation when solver state was created on transient request worker threads. MILP calls now execute serially on one persistent worker with native HiGHS `threads=1`; regression tests cover repeated and concurrent API requests. The final backend run passes 41 tests. The upstream scheduler and parallelism limitation is described in [HiGHS documentation](https://ergo-code.github.io/HiGHS/dev/parallel/).
