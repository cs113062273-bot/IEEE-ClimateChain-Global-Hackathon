# Sample data attribution and status

**Supported by National Energy SO Open Data.**

`intervals.json` contains an attributed transformed subset of national GB carbon-intensity estimates and historical demand context from the [National Energy System Operator data portal](https://www.neso.energy/data-portal/national-carbon-intensity-forecast), under the [NESO Open Data Licence](https://www.neso.energy/data-portal/neso-open-licence). A separate [Carbon Intensity API](https://api.carbonintensity.org.uk/) crosscheck is subject to [CC BY 4.0 and API terms](https://github.com/carbon-intensity/terms/).

Weather data by [Open-Meteo.com](https://open-meteo.com/), using ERA5 / Copernicus Climate Change Service / ECMWF, under [CC BY 4.0 and Open-Meteo terms](https://open-meteo.com/en/terms). Free API acquisition is for this noncommercial educational prototype. Changes: UTC alignment; preceding-hour radiation divided into two half-hour means; instantaneous weather linearly interpolated. The result is historical reanalysis, with derived temporal resolution.

`pvgis_seasonal.json` is a monthly aggregation of the real PVGIS 5.3 SARAH3 **2023** hourly model for a hypothetical 20-kWp London system. Credit: European Commission Joint Research Centre, PVGIS and CM SAF SARAH3. The [official manual](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en) permits use of results; [EC reuse policy](https://commission.europa.eu/legal-notice_en) applies with its third-party-rights caveat. Changes: modeled watts integrated to monthly kWh.

Source URLs, actual retrieval times, raw SHA256 and transformations are embedded in the JSON and recorded in `data/manifests/sources.json`. Bulk snapshots can be reacquired with the scripts. These source licences remain distinct from the repository's code licence. None of the providers endorses GridProof.

The fixture has no measured campus consumption, EV, battery, PV production or actual tariff. Those are simulated by the scenario engine. The historical published carbon forecast has no verified issue time. No data or integrity hash creates a certified carbon credit or proves causal avoided emissions.
