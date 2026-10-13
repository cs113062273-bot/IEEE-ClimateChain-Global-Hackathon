# Acquisition worklog

2026-10-13, Phase A / G0. Read the implementation contract and start prompt; independently browsed official contest pages, Carbon Intensity terms, NESO source pages/licence, Open-Meteo historical API/terms and PVGIS manual/API before downloading. Direct discovery cache subsequently documented Devpost/NESO HTML HTTP 403 challenges while browser reads succeeded. No authenticated accounts or challenge bypass used.

Executed `python scripts/fetch_neso.py --year 2025`: successful official bounded CKAN SQL response, 17,520 intervals, plus real historic demand CSV with 17,520 rows. Crosschecked January 1 interval start semantics with a cached Carbon Intensity API response. Demand DST mapping produced 46 periods on March 30 and 50 on October 26. 43 missing 2025 actual/forecast CI values retained as null, no replacement.

Executed `python scripts/fetch_neso.py --year 2026 --ci-only`: 13,690 rows through 2026-10-13T05:00:00Z exclusive, bounded by the actual last completed interval at retrieval. One missing actual retained. Initial current-day query returned future forecasts; the final query deliberately caps to completed intervals rather than including current-day future outcomes.

Executed `python scripts/fetch_openmeteo.py`: one successful cached explicit ERA5 London request, 8,784 hourly records (2025 plus one padding day), no missing requested variables. The official preceding-hour definition of radiation is respected in the join; this is historical reanalysis and cannot be treated as prediction-time weather.

Executed `python scripts/fetch_pvgis.py --year 2023`: v5.3 SARAH3 documented years are 2005–2023; downloaded 8,760 real modeled records for supported 2023. Preserved JSON inputs/meta; monthly summary annual integral 20,140.0634 kWh for hypothetical 20 kWp, 14% loss, 35° tilt, south aspect. This is a seasonal model reference, not observed 2025 production.

Executed `python scripts/fetch_ukpn_sample.py`: public catalogue metadata HTTP 200, but 100-record consumption sample HTTP 403 ForbiddenAccess. Recorded the exact error and omitted optional load source. No household corpus downloaded.

Executed `python scripts/build_snapshot.py`: 17,520 UTC joined half-hours, 96 two-day sample intervals, 672 prior-week real records for offline past-only forecasting. Samples have complete actual CI. Repeat build produces the same fixture bytes from fixed input snapshots; generated timestamps use source acquisition time.

Executed `python scripts/validate_sources.py --require-bulk`: all raw/normalized/sample digests and indices checked; required sources available. Source audit records real bytes/counts/hashes. `python -m unittest discover -s scripts/tests -v` passes data tests for DST, UTC/null handling, duplicates/gaps/out-of-order records, preceding-hour radiation energy conservation, rate-limit retries and authentic fixture coverage/hash. `python scripts/profile_sources.py` produced and visually inspected source diagnostic plots. Exact audit and tests are retained under `data/manifests/`.

Working inputs communicated to backend owner: `data/sample/intervals.json` with metadata, intervals and history_intervals; full `data/processed/intervals_2025.csv`, `neso_ci_2025.csv`, `neso_ci_2026.csv`, `weather_2025.csv`, `neso_demand_2025.csv`; manifests; PVGIS summary. Backend must model site load/PV/battery/prices and explicitly distinguish them from real grid context.

Known limits: national average, not London marginal intensity; retrospective forecasts have no verified issuance; weather is reanalysis; 43 missing 2025 CI points; UKPN restricted; hypothetical campus/PV/costs. G0 does not validate any modeled savings, deployment, public submission, personal eligibility or award result.
