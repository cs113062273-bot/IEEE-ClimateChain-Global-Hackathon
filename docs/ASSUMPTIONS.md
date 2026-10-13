# Modeling assumptions

GridProof uses authentic national GB carbon estimates and historical London ERA 5 reanalysis to replay a **hypothetical** campus. Every load, job, battery and tariff below is a declared simulation assumption. The prototype has no connected physical electricity meters.

| Quantity | Assumption and units | Status |
|---|---|---|
| Resolution | 48 consecutive half-hour UTC `[start,end)` intervals, `dt=0.5 h` | Model |
| Rooftop | 20 kWp default, adjustable | Hypothetical |
| PV decision forecast | Calendar daylight sinusoid, seasonal peak factor `0.58+0.20 sin(2π(day-of-year−80)/365)`; no future observed weather | Modeled forecast |
| PV replay outcome | `20 kWp × 0.5 h × 0.8 × clip(ERA5 shortwave W/m² /1000, 0, 1)` | Modeled from historical reanalysis |
| Fixed campus load | 6 kW at night; +8 kW 08:00–18:00 UTC; +2 kW 18:00–22:00 UTC, 232 kWh/day | Synthetic |
| Flexible EVs | Fleet A:24 kWh, slots 14–35, 11 kW; Fleet B:18 kWh, slots 16–39, 11 kW; shared station 22 kW | Synthetic requirements |
| Compute batch | 20 kWh in 4 contiguous half-hours; earliest start 12, latest end 42; max concurrency 1 | Synthetic requirement |
| Battery | 40 kWh; SoC 10–90%; initial and terminal 50%; charge/discharge 10 kW; both one-way efficiencies 0.95 | Hypothetical device |
| Tariff | £0.12/kWh 00:00–07:00 UTC; £0.36 16:00–20:00; £0.23 otherwise | Illustrative; no actual bill claim |
| Import | 60 kW cap; no export; excess PV curtailed | Model boundary |
| Emissions | `Σ import_kWh × actual_gCO2_per_kWh /1000` | Modeled location-based exposure |

EV deadlines are exclusive slot indices: deadline 36 means energy must finish by 18:00 UTC. Battery capacity edits preserve the configured initial/terminal fractions, preventing terminal energy borrowing. No device simultaneously charges and discharges. EV energy is exact; batch starts are binary and contiguous. An infeasible comparison returns a meaningful 422 error, preserving the last valid UI result. A solver failure or timeout without an incumbent may use a numerically verified immediate fallback, explicitly labeled `fallback_immediate`.

The primary decision is issued at 00:00 UTC. Carbon predictors use only observations strictly before that time and predetermined calendar features. Weather, generation, demand and actual carbon from the outcome day never become decision features. Historical NESO forecasts are a secondary comparison because issue-time provenance was not verified. Perfect future carbon is separately labeled **unrealistic oracle**; its solar forecast still uses the calendar assumption, so it is an information comparison rather than a strict outcome optimization bound.

After scheduling, EV/batch/battery decisions stay fixed. Replay replaces forecast solar with radiation-derived modeled solar and recomputes grid imports and PV curtailment to balance energy. This is balancing recourse, not retrospective rescheduling. Replay checks the grid cap again; a violation cannot receive a verified-feasible claim. `pv_forecast_kwh` and `grid_import_forecast_kwh` preserve the decision quantities; exposed `pv_available_kwh` and `grid_import_kwh` describe replay outcomes. All policies share identical jobs, battery boundaries, carbon outcomes, irradiance and tariff assumptions. Immediate charging follows input job order at the first allowed slot under the shared charger cap; the immediate battery stays idle.

The simple PV model uses horizontal shortwave radiation without tilted-plane transposition, temperature correction, shadows, inverter detail or field calibration. Its 2025 annual modeled energy is 18,262.272 kWh for 20 kWp. PVGIS 5.3 SARAH3's separate 2023 London 35° tilted 20-kWp model produces 20,140.0634 kWh; the twelve monthly totals have Pearson correlation 0.9454. This is an engineering scale/season sanity check, **not** validation against measurements or a same-year accuracy claim. The winter difference is substantial. See `experiments/solar_model_diagnostic.csv`; weather response timing/alignment is documented in `DATA_CATALOG.md`.

Hybrid minimizes `w × predicted_kgCO2/50 +(1−w) × illustrative_GBP/100`, with `w=0.7` by default. Carbon-first uses `w=1`; cost-first uses `w=0`. A disclosed `1e−7` per battery-throughput kWh breaks otherwise equivalent solutions; it is not a calibrated battery degradation model. Objectives do not award separate PV offsets or export credits. This system estimates average location-based grid exposure, not marginal, causal avoided physical emissions, tradable credits, RECs or certified offsets.

The local registry attests a report fingerprint and protocol scope uniqueness. Site identity and source truth are not authenticated by a blockchain. No public chain, paid deployment, regulatory credit or electricity market operation is claimed.

Validation-based model selection is usable from September 1, after the July–August validation window closes. January and August demo decisions therefore use the past-only seasonal median. Historical publication latency of past actual CI observations is not archived; availability at the midnight issue is an explicit assumption. Forecast metadata includes training window, selection end, usable-from time and model weights digest where applicable.
