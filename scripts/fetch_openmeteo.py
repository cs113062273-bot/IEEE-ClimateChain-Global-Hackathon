"""Acquire noncommercial London 2025 hourly weather reanalysis."""
import argparse
import json
import urllib.parse
from datetime import timedelta
from acquisition import *

if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--refresh",action="store_true"); args=p.parse_args()
    params={"latitude":51.5074,"longitude":-0.1278,"start_date":"2025-01-01","end_date":"2026-01-01",
            "hourly":"temperature_2m,shortwave_radiation,cloud_cover,wind_speed_10m","timezone":"UTC","models":"era5","wind_speed_unit":"kmh"}
    url="https://archive-api.open-meteo.com/v1/archive?"+urllib.parse.urlencode(params)
    source_id="openmeteo-london-weather-2025"
    try:
        body,meta=fetch(url,RAW/"openmeteo_london_2025.json",refresh=args.refresh)
        d=json.loads(body); h=d["hourly"]
        if d["utc_offset_seconds"]!=0 or any(len(v)!=len(h["time"]) for v in h.values()):
            raise ValueError("Weather schema/timezone/array length mismatch")
        rows=[]
        for i,t in enumerate(h["time"]):
            a=parse_utc(t,allow_naive=True)
            rows.append({"start_utc":utc_text(a),"end_utc":utc_text(a+timedelta(hours=1)),
                         "temperature_2m":numeric(h["temperature_2m"][i]),"shortwave_radiation_w_per_m2":numeric(h["shortwave_radiation"][i]),
                         "cloud_cover_percent":numeric(h["cloud_cover"][i]),"wind_speed_10m_kmh":numeric(h["wind_speed_10m"][i])})
        out=PROCESSED/"weather_2025.csv"; write_csv(out,rows)
        record(source_id,status="verified",license="CC-BY-4.0",license_url="https://open-meteo.com/en/terms",attribution="Weather data by Open-Meteo.com; ERA5 reanalysis, Copernicus Climate Change Service / ECMWF",original_url=url,
               source_page="https://open-meteo.com/en/docs/historical-weather-api",**meta,processed_path=relative(out),processed_sha256=sha256(out),**profile(rows,60),
               units=d["hourly_units"],provenance_status="historical_reanalysis",model="ERA5",coordinates_requested=[51.5074,-0.1278],coordinates_returned=[d["latitude"],d["longitude"]],
               transformations=["Requested UTC; numeric conversion without imputation", "Extra 2026-01-01 day provides preceding-hour radiation and next-hour interpolation at 2025 end"],
               limitations=["Not observed site weather or historical issued forecast", "Shortwave radiation timestamp denotes preceding-hour mean", "Instantaneous variables at timestamp; half-hour values derived later", "Grid cell differs from requested coordinates"],
               access_limitations="Free API noncommercial only; <600 calls/min, <5000/hour, <10000/day; this script makes one cached request")
    except Exception as exc:
        record(source_id,status="failed",original_url=url,error=str(exc),license_url="https://open-meteo.com/en/terms")
        raise
