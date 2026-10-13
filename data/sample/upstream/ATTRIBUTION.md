# Original-byte source support fixtures

**Supported by National Energy SO Open Data.**

`neso_ci_2025.json` is the original bounded 2025 response from the NESO public CKAN API. Its complete original bytes are preserved, including the official historical estimated actual/forecast values, nulls and UTC timestamps. Source URL, retrieval time and SHA256 appear in the separately distributed `data/trust/source_anchors.v1.json`. Reuse is under the [NESO Open Data Licence](https://www.neso.energy/data-portal/neso-open-licence); no endorsement is implied.

`openmeteo_london_2025.json` is the original London ERA5 hourly API response (2025 plus one padding day), attributed to [Open-Meteo.com](https://open-meteo.com/), Copernicus Climate Change Service and ECMWF. It is [CC BY 4.0 data](https://open-meteo.com/en/terms), acquired for this noncommercial educational prototype. The source file is unmodified; half-hour radiation/PV transformations occur separately during reconstruction.

These approximately 2 MB support fixtures enable new evidence production without downloading bulk files. A v2 report embeds original bytes so its verifier can operate from the report and an independently trusted anchor manifest. A report's own newly computed source hash is insufficient: it must match that separate trusted manifest. HTTPS acquisition digests establish consistency with the pinned downloaded snapshots, not signed provider authentication, physical meter truth, historical publication-time availability or certified avoided emissions.
