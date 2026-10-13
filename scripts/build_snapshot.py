"""Offline normalize/join authenticated snapshots and build the attributed demo sample."""
import argparse
import json
from datetime import timedelta
from acquisition import *

SOURCES=["neso-national-ci-2025","neso-demand-2025","openmeteo-london-weather-2025"]
NUMERIC_FIELDS=["grid_ci_actual_g_per_kwh","grid_ci_forecast_g_per_kwh","grid_demand_mw","embedded_wind_generation_mw","embedded_solar_generation_mw","temperature_2m","cloud_cover_percent","wind_speed_10m_kmh","shortwave_radiation_w_per_m2"]


def weather_halfhour(weather,start):
    hour=start.replace(minute=0,second=0,microsecond=0)
    a=weather[utc_text(hour)]; b=weather[utc_text(hour+timedelta(hours=1))]
    fraction=(start-hour).total_seconds()/3600
    out={}
    for field in ["temperature_2m","cloud_cover_percent","wind_speed_10m_kmh"]:
        x,y=numeric(a[field]),numeric(b[field])
        out[field]=round(x+(y-x)*fraction,6) if x is not None and y is not None else None
    # Radiation at h+1 averages [h,h+1); both half-hours retain that mean.
    out["shortwave_radiation_w_per_m2"]=numeric(b["shortwave_radiation_w_per_m2"])
    return out


def build(dates,history_days=7):
    dates=sorted(set(dates))
    ci=csv_rows(PROCESSED/"neso_ci_2025.csv")
    weather={r["start_utc"]:r for r in csv_rows(PROCESSED/"weather_2025.csv")}
    demand={r["start_utc"]:r for r in csv_rows(PROCESSED/"neso_demand_2025.csv")}
    rows=[]
    for r in ci:
        a=parse_utc(r["start_utc"])
        item={k:r[k] for k in ["start_utc","end_utc","grid_ci_actual_g_per_kwh","grid_ci_forecast_g_per_kwh"]}
        item.update(weather_halfhour(weather,a))
        for field in ["grid_demand_mw","embedded_wind_generation_mw","embedded_solar_generation_mw"]:
            item[field]=demand.get(r["start_utc"],{}).get(field)
        for field in NUMERIC_FIELDS:
            item[field]=numeric(item[field])
        rows.append(item)
    full=PROCESSED/"intervals_2025.csv";write_csv(full,rows)
    snapshots=[json.loads((MANIFEST/"artifacts"/(s+".json")).read_text(encoding="utf-8")) for s in SOURCES]
    # Output bytes depend on source snapshots and options, never the build wall clock.
    metadata={"schema_version":"1.0.0","created_utc":max(s["fetched_utc"] for s in snapshots),"client_context_date":"2026-10-13","location":{"anchor":"London, Great Britain","latitude":51.5074,"longitude":-0.1278},
              "interval_semantics":"UTC [start_utc,end_utc)","dt_hours":0.5,"dates":dates,"history_days":history_days,"provenance_status":"authentic_grid_estimates_with_historical_weather_reanalysis; facility simulated separately",
              "units":{"grid_ci_actual_g_per_kwh":"gCO2/kWh","grid_ci_forecast_g_per_kwh":"gCO2/kWh","shortwave_radiation_w_per_m2":"W/m2","temperature_2m":"C","cloud_cover_percent":"%","wind_speed_10m_kmh":"km/h","grid_demand_mw":"MW"},
              "neso_required_attribution":"Supported by National Energy SO Open Data",
              "attribution":[{"provider":"National Energy System Operator / Carbon Intensity API","url":"https://www.neso.energy/data-portal/national-carbon-intensity-forecast","license":"NESO Open Data Licence; Carbon API CC-BY-4.0","license_url":"https://www.neso.energy/data-portal/neso-open-licence"},
                             {"provider":"National Energy System Operator, Historic Demand Data","url":"https://www.neso.energy/data-portal/historic-demand-data","license":"NESO Open Data Licence"},
                             {"provider":"Open-Meteo.com / Copernicus Climate Change Service / ECMWF ERA5","url":"https://open-meteo.com/","license":"CC-BY-4.0","license_url":"https://open-meteo.com/en/terms"}],
              "transformations":["CI retained exactly; no imputation", "GB settlement mapped with Europe/London DST", "Radiation at hour h+1 copied to both half-hours starting hour h because source denotes preceding-hour mean; energy conserved", "Temperature/cloud/wind linearly interpolated to half-hour interval starts from hourly endpoints", f"{history_days} prior days per sample date retained for offline past-only forecasts"],
              "limitations":["National GB average carbon estimate, not London marginal emissions", "Historic published forecast issuance unverified", "Weather reanalysis is retrospective; future weather unavailable at historical decision time", "Half-hour weather resolution is derived; no new observational precision", "No site meter, solar, fixed-load or tariff measurements"],
              "source_snapshots":[{k:s.get(k) for k in ["source_id","original_url","source_page","fetched_utc","license","license_url","attribution","path","sha256","processed_path","processed_sha256","row_count","coverage_start_utc","coverage_end_utc_exclusive","missing_count","provenance_status"]} for s in snapshots]}
    sample=[];history=[]
    for r in rows:
        a=parse_utc(r["start_utc"])
        matching=any(r["start_utc"][:10]==d for d in dates)
        prior=any(parse_utc(d+"T00:00:00Z")-timedelta(days=history_days)<=a<parse_utc(d+"T00:00:00Z") for d in dates)
        if matching or prior:
            item={**r,"source_refs":SOURCES,"quality_flags":["national_gb_ci","historic_forecast_issuance_unverified","weather_reanalysis","weather_halfhour_derived","facility_modeled_separately"]}
            (sample if matching else history).append(item)
    for d in dates:
        day=[r for r in sample if r["start_utc"][:10]==d]
        if len(day)!=48 or any(r["grid_ci_actual_g_per_kwh"] is None for r in day):
            raise ValueError(f"Sample date {d} missing authentic actual CI")
    out=ROOT/"data/sample/intervals.json";write_json(out,{"metadata":metadata,"intervals":sample,"history_intervals":history})
    write_csv(ROOT/"data/sample/ci_history.csv",sorted(history+sample,key=lambda x:x["start_utc"]))
    record("gridproof-normalized-2025",status="verified",license="Source licences apply; derived transformations by GridProof",attribution="NESO and Open-Meteo / ECMWF",original_url=None,
           path=relative(full),sha256=sha256(full),byte_size=full.stat().st_size,fetched_utc=metadata["created_utc"],processed_path=relative(full),processed_sha256=sha256(full),**profile(rows),
           units=metadata["units"],provenance_status=metadata["provenance_status"],lineage=SOURCES,transformations=metadata["transformations"],limitations=metadata["limitations"])
    record("gridproof-offline-sample",status="verified",license="NESO Open Data Licence and Open-Meteo CC-BY-4.0; attributed transformed subset",attribution="NESO; Open-Meteo / ECMWF ERA5",original_url=None,
           path=relative(out),sha256=sha256(out),byte_size=out.stat().st_size,fetched_utc=metadata["created_utc"],row_count=len(sample),history_row_count=len(history),columns=list(sample[0]),timezone="UTC",granularity_minutes=30,
           dates=dates,http_status=None,content_type="application/json",etag=None,units=metadata["units"],
           coverage_intervals=[{"start_utc":d+"T00:00:00Z","end_utc":utc_text(parse_utc(d+"T00:00:00Z")+timedelta(days=1))} for d in dates],
           profile_by_date={d:profile([r for r in sample if r["start_utc"].startswith(d)]) for d in dates},
           license_urls=["https://www.neso.energy/data-portal/neso-open-licence","https://open-meteo.com/en/terms"],
           provenance_status=metadata["provenance_status"],lineage=SOURCES,transformations=metadata["transformations"],limitations=metadata["limitations"])
    print(f"SNAPSHOT {len(rows)} normalized intervals; {len(sample)} sample intervals + {len(history)} prior history; sha256={sha256(out)}")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--dates",nargs="+",default=["2025-01-15","2025-08-12","2025-09-01","2025-10-13"]);p.add_argument("--history-days",type=int,default=14);args=p.parse_args();build(args.dates,args.history_days)
