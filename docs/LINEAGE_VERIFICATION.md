# Source-to-input verification, evidence v2

Evidence v2 closes the review's zero-CI rehash gap. The verifier independently reconstructs each actual CI, scheduling forecast, preceding-hour radiation, forecast/modelled solar, fixed campus load and illustrative tariff from separately pinned original sources and a supported transformation specification. An internally consistent new report with all actual CI values and carbon KPIs rewritten to zero fails **source lineage**, even when its new digest and physical arithmetic are valid.

The system preserves the existing architecture, source history, original two demo windows and v1 reports. It does not certify provider measurements, historical issue-time data availability, causal avoided emissions or solver optimality. No new chain deployment or public publication is part of this repair.

## Four separate levels

`levels.integrity` compares the canonical report with the expected digest. The caller must obtain that digest from the intended commitment or another trusted channel; a report and its own freely recomputed digest only demonstrate internal consistency.

`levels.source_lineage` verifies original-byte upstream hashes against the **external** `data/trust/source_anchors.v1.json`, independently reconstructs all relevant inputs and checks frozen configuration, model metadata, baseline policy and decision/outcome solar distinctions.

`levels.physical_validity` checks half-hour energy balance, battery dynamics/power/SoC, grid and peak caps, EV/batch requirements and result arithmetic. This layer can be true for internally feasible fabricated zero-CI inputs while source lineage is false; the distinction is deliberate.

`levels.onchain_attestation` is `NOT_CHECKED` in the offline verifier. Receipt/event/registry verification is a separate operation. Top-level `verified=true` means the first three local levels pass; it does not imply an onchain check or physical emissions certification.

| Case | Overall local verdict |
|---|---|
| v2, trusted original bytes, correctly reconstructed inputs and feasible arithmetic | `VERIFIED` |
| Changed report checked against original expected digest | `HASH_MISMATCH` |
| New digest but fabricated CI/PV/forecast/load/tariff or altered transform | `INVALID_EVIDENCE` |
| Necessary original bytes/model or external trusted anchor set unavailable | `INCOMPLETE` |
| Internally valid v1 report without independently reconstructible lineage | `INTEGRITY_ONLY` |

Historical current-checkout artifact drift is a warning: a self-contained report is checked against its authentic embedded bytes and trusted pins rather than requiring today's code/sample files to equal an earlier producer checkout. `artifact_checks` explicitly marks each local artifact `MATCHED`, `MISMATCH`, `NOT_LOCALLY_CHECKED` or `NOT_REQUESTED`; these are distinct from successful source reconstruction. V1 reports are not silently upgraded or overwritten. Missing bulk files are warnings when authentic embedded bytes and external pins suffice; missing all representations of necessary source bytes or missing external pins is incomplete.

Source snapshot roles are explicit. CI/weather are `original_input` and required; a trained portable forecast is `decision_model` and required on model days. The sample fixture is `derived_support`: its local fingerprint supports reproduction, while the full embedded original bytes permit independent reconstruction without that derived file. Demand references are `context_only` and PVGIS is `diagnostic_only`; they are not listed as required input snapshots because production forecasting/scheduling consumes neither. Source lineage reports the actual embedded/local representation used, rather than treating every source ID in contextual UI metadata as a verified necessary input.

## Trust strategy and self-contained bundles

The external anchor manifest fixes the existing full-year NESO response SHA256 `0c07bc094561e19c61826b693395b92e8334a34b613e5525ca016ae6c91fc815` and Open-Meteo response SHA256 `6098ffc0ecac7610670f34efcd4322717b04a9fdaba5a666ed265ce066506edd`. Those values originate from the actual earlier HTTPS acquisitions, with source URLs, attribution, licences and retrieval times retained. It also fixes the portable trained model hash.

The anchor manifest is distributed separately from evidence in the trusted checkout. The verifier never accepts a report's self-reported replacement anchor manifest. An evaluator should obtain these pins through a trusted repository/commit or independently reacquire and inspect the particular provider snapshot. Historical upstream revisions may legitimately produce different newly acquired hashes; that requires an explicit new trust anchor/version rather than accepting whatever the submitted report says. The upstream services did not digitally sign these responses; this design proves correspondence with the pinned acquisition, not universal data truth.

`data/sample/upstream/` preserves the two original responses (approximately 2 MB total), with licence/attribution in its accompanying file. This is a bounded support fixture, not the large household corpus. V2 evidence carries these source bytes as deterministic gzip plus base64, reducing transport/storage size without changing any original byte. Decompression is bounded, and the trusted SHA256 covers the original decompressed response. Uncompressed base64 bundles remain readable. For a trained forecast it additionally carries pinned portable model JSON using the same transport. The report is self-contained for data and model reconstruction, while the trusted anchor manifest remains external so the report cannot certify its own rewritten data. A standalone verifier can run in a directory without backend, pandas, LightGBM, pickle or bulk datasets.

## Fixed transformations and configurable simulated scenarios

The independent verifier implements `gridproof-input-transforms-v1` directly and does not import the producer's code. It rejects modified transform configuration even when that configuration's own digest is recomputed. Values are checked to a numerical tolerance accommodating the documented nine-decimal canonical representation.

- NESO portal `datetime` is the UTC half-hour start; null actual values cannot be replaced by forecast or zero.
- Radiation at hour `h+1` describes the preceding hour `[h,h+1)`. Both half-hours use that mean, preserving energy.
- Realized modeled PV is `solar_kwp × 0.5 × 0.8 × clip(radiation/1000,0,1)` kWh per half-hour.
- Scheduling PV uses the existing calendar sine model. `peak_first` instead declares zero decision PV, while retaining the same realized radiation-derived PV.
- Fixed load is the declared UTC synthetic weekday-independent campus formula; tariffs remain the explicit UTC illustrative 0.12/0.23/0.36 GBP/kWh schedule.
- Forecasts use only original CI before midnight and calendar features. Published NESO forecast is independently mapped but remains issuance-unverified and secondary.
- The declared Immediate baseline is independently reconstructed as earliest feasible EVs under the shared station cap, earliest contiguous batches and idle battery. A convenient but worse feasible schedule cannot masquerade as that reference.

The scenario may legitimately change through the user's simulation controls. Its full parameters must agree between `scenario_parameters`, `inputs.scenario`, the frozen configuration and scenario digest. Policy-specific peak-aware scenario parameters are recorded accurately. Configuration checks do not assert an actual facility or prevent legitimate new simulations. An optional externally supplied configuration digest verifies that a particular previously chosen scenario/configuration has been preserved across reports.

## Portable trained model

`experiments/models_portable/carbon_model.json` stores the original LightGBM numeric regression tree structures and frozen metadata; `metadata.json` records training, validation-selection availability, original pickle fingerprint and portable fingerprint. The portable file is independently pinned by SHA256 `039425d1c48981a2a377b7eec4d33a72da809cda9cae1edf5dce21c62e2d5f49`.

`scripts/verify_evidence.py` reconstructs the 15 past-only features with the standard library and traverses those trees directly. It neither imports backend nor executes submitted pickle. Model inference matched the original Booster with maximum error **0.0** on September 1's 48 intervals. Independent feature reconstruction across all **122 September–December days** matched production inference with maximum prediction difference **0.0**. This reproduces inference, not model retraining or proof that AI improves scheduling.

The model's validation selection is unavailable before September 1. Earlier demo days remain the seven-day seasonal median. Reported model hash, artifact format, training window, availability gate, issue time and latest history timestamp must match the reconstructed method. Publication latency and retrospective revisions remain explicit assumptions.

## Run and test

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_lineage.py -q
.\.venv\Scripts\python.exe scripts/verify_evidence.py path\to\new-v2-proof.json --digest 0x<trusted-expected-report-digest>
```

To validate a specific previously committed configuration, add `--expected-config-digest <trusted-config-sha256>`. To run without backend, copy the standalone verifier and `data/trust/source_anchors.v1.json` into a clean directory, supply the self-contained report and use `python -I verify_evidence.py proof.json --root <clean-directory>`.

Attack tests cover a fully rehashed zero-CI report, rewritten source blob plus self-declared new hash, arbitrary radiation/PV/forecast/load/tariff, rewritten model issue/configuration, missing raw/model/anchors, valid user scenario changes, both peak policies, legacy degradation and independent execution without backend imports. Original v1 fixtures remain available for historical inspection; final v2 demo evidence is generated only after the integration files stabilize.
