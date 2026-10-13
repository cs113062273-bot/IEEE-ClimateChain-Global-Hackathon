"""PVGIS 5.3 supported-year London model, deliberately separate from 2025 observations."""
import argparse
import calendar
import json
import urllib.parse
from acquisition import *

MANUAL = "https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/pvgis-5-user-manual_en"

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--year",type=int,default=2023); p.add_argument("--refresh",action="store_true"); args=p.parse_args()
    if not 2005 <= args.year <= 2023:
        p.error("PVGIS 5.3 SARAH3 official documented coverage 2005–2023; 2025 unsupported")
    params={"lat":51.5074,"lon":-0.1278,"startyear":args.year,"endyear":args.year,"raddatabase":"PVGIS-SARAH3",
            "pvcalculation":1,"peakpower":20,"loss":14,"angle":35,"aspect":0,"pvtechchoice":"crystSi","outputformat":"json"}
    url="https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?"+urllib.parse.urlencode(params)
    source_id=f"pvgis-london-pv-model-{args.year}"
    try:
        body,meta=fetch(url,RAW/f"pvgis_london_{args.year}.json",refresh=args.refresh,timeout=60)
        d=json.loads(body); h=d["outputs"]["hourly"]
        if not h or not all("P" in row and "time" in row for row in h):
            raise ValueError("PVGIS outputs.hourly schema changed")
        monthly={i:0.0 for i in range(1,13)}
        for r in h:
            monthly[int(r["time"][4:6])]+=float(r["P"])/1000
        summary={"metadata":{"source_id":source_id,"attribution":"European Commission Joint Research Centre, PVGIS 5.3 / CM SAF SARAH3",
                             "license":"PVGIS results freely usable per official manual; EC reuse policy subject to third-party rights",
                             "license_url":MANUAL,"source_url":url,"raw_sha256":meta["sha256"],"retrieved_utc":meta["fetched_utc"],
                             "provenance_status":"modeled_pv_potential","parameters":params,"limitations":["2023 climate baseline, not 2025 production", "Hypothetical 20-kWp system, not a metered campus", "PVGIS SARAH3 hourly timestamp minute preserved in raw; monthly energy assumes one-hour spacing"]},
                 "monthly_model_energy_kwh":[{"month":m,"energy_kwh":round(e,6),"mean_daily_kwh":round(e/calendar.monthrange(args.year,m)[1],6)} for m,e in monthly.items()],
                 "annual_model_energy_kwh":round(sum(monthly.values()),6)}
        out=ROOT/"data/sample/pvgis_seasonal.json"; write_json(out,summary)
        times=[datetime.strptime(r["time"],"%Y%m%d:%H%M").replace(tzinfo=UTC) for r in h]
        gaps=sum(b-a!=timedelta(hours=1) for a,b in zip(times,times[1:]))
        record(source_id,status="verified",license=summary["metadata"]["license"],license_url=MANUAL,attribution=summary["metadata"]["attribution"],original_url=url,
               **meta,row_count=len(h),columns=list(h[0]),column_types={k:"string" if k=="time" else "number" for k in h[0]},
               coverage_start_utc=utc_text(min(times)),coverage_end_utc_exclusive=utc_text(max(times)+timedelta(hours=1)),granularity_minutes=60,timezone="UTC",
               missing_count={k:sum(r.get(k) is None for r in h) for k in h[0]},missing_rate={k:sum(r.get(k) is None for r in h)/len(h) for k in h[0]},gap_count=gaps,
               units={"P":"W","G(i)":"W/m2","T2m":"C","WS10m":"m/s"},provenance_status="modeled_pv_potential",parameters=params,
               supported_years=[2005,2023],processed_path=relative(out),processed_sha256=sha256(out),
               transformations=["Raw full JSON inputs/meta retained", "Hourly modeled P [W] integrated over one-hour steps into monthly kWh"],
               limitations=summary["metadata"]["limitations"],access_limitations="Public GET; 30 calls/second official limit; one cached request with bounded retry")
    except Exception as exc:
        record(source_id,status="failed",original_url=url,error=str(exc),license_url=MANUAL,supported_years=[2005,2023],provenance_status="modeled_pv_potential")
        print(f"PVGIS unavailable: {exc}")
        raise SystemExit(1)
