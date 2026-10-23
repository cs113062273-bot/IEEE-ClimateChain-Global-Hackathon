# Source attribution

GridProof is an independent prototype. Its use of public data does not imply provider endorsement.

| Source | Use | Terms and attribution |
| --- | --- | --- |
| [National Energy System Operator](https://www.neso.energy/data-portal/national-carbon-intensity-forecast) / [Carbon Intensity API](https://api.carbonintensity.org.uk/) | National GB historical grid carbon intensity, historical forecasts | NESO portal licence and API CC BY 4.0; consult the verified manifest and [API terms](https://github.com/carbon-intensity/terms/) |
| [NESO historic demand](https://www.neso.energy/data-portal/historic-demand-data) | National demand and embedded wind/solar context | NESO Open Data Licence; revisions and settlement time conversion documented in catalog |
| [Open-Meteo](https://open-meteo.com/) | London historical weather reanalysis | [CC BY 4.0, noncommercial free API terms](https://open-meteo.com/en/terms); weather is reanalysis, not an issued forecast |
| [de Bont, Hoogsteen, Hurink, Kokhuis, Kusche et al. (2025), Electric Vehicle Charging Session Data of Large Office Parking Lot, 4TU.ResearchData, v2](https://doi.org/10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2) (SmoothEMS met GridShield; University of Twente, a.s.r., ElaadNL, MENNEKES, Kropman, Amperapark) | Real workplace charging sessions (arrival, departure, energy, pseudonymous driver ID) for the car-park controller, departure-risk model and held-out evaluation | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). Non-commercial research use. Downloaded by `scripts/fetch_workplace_sessions.py` and **not redistributed** here; the dataset README asks users to consult its contacts before sharing transformed data, so session-level derivatives and trained departure models stay in gitignored folders. Committed outputs are day-level aggregates and statistics. |
| [European Commission Joint Research Centre, PVGIS](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis_en) | Modelled historical photovoltaic production potential, if successfully acquired | European Commission reuse terms as verified in catalog; hypothetical site, not observed generation |

The downloaded manifest is the source of truth for acquisition status, original URLs, retrieval timestamps, raw and transformed digests, units and limitations. Optional sources are only used if their access and reuse terms are established. Site building demand, the original fleet EV jobs, battery operation, 2025 rooftop production and tariffs are simulated or illustrative.

Original project code is MIT. This does not relicense upstream data or third-party dependencies. Small shared source excerpts retain their original attribution and licence conditions.
