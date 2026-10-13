"""Cache official documentation/terms with exact acquisition times and HTTP evidence."""
import argparse
from acquisition import *

PAGES={
 "competition-overview":"https://ieee-climatechain-hack.devpost.com/",
 "competition-rules":"https://ieee-climatechain-hack.devpost.com/rules",
 "competition-updates":"https://ieee-climatechain-hack.devpost.com/updates",
 "competition-gallery":"https://ieee-climatechain-hack.devpost.com/project-gallery",
 "neso-ci-docs":"https://www.neso.energy/data-portal/national-carbon-intensity-forecast",
 "neso-demand-docs":"https://www.neso.energy/data-portal/historic-demand-data",
 "neso-license":"https://www.neso.energy/data-portal/neso-open-licence",
 "carbon-api-docs":"https://api.carbonintensity.org.uk/",
 "carbon-api-terms":"https://raw.githubusercontent.com/carbon-intensity/terms/master/README.md",
 "openmeteo-docs":"https://open-meteo.com/en/docs/historical-weather-api",
 "openmeteo-terms":"https://open-meteo.com/en/terms",
 "pvgis-docs":"https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en",
 "pvgis-manual":"https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en",
 "ukpn-docs":"https://ukpowernetworks.opendatasoft.com/explore/dataset/ukpn-smart-meter-consumption-lv-feeder/?tab=metas"
}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--refresh",action="store_true");args=p.parse_args()
    entries=[]
    for source_id,url in PAGES.items():
        try:
            _,meta=fetch(url,RAW/"discovery"/(source_id+".html"),refresh=args.refresh,attempts=2,timeout=25)
            entries.append({"source_id":source_id,"status":"retrieved",**meta})
        except Exception as exc:
            entries.append({"source_id":source_id,"status":"failed","url":url,"checked_utc":now_utc(),"error":str(exc)})
            print(f"DOCS {source_id}: {exc}",flush=True)
    write_json(MANIFEST/"discovery.json",{"client_context_date":"2026-10-13","checked_utc":now_utc(),"pages":entries,
                                            "note":"Docs independently browsed before data acquisition; this records local cached HTTP evidence. Runtime clock is recorded as returned, not overwritten with client date."})
