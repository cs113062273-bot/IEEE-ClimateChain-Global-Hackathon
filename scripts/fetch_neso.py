"""Fetch selected years of national CI and one official demand CSV, never full archive."""
import argparse
import json
import urllib.parse
from datetime import timedelta
from acquisition import *

RESOURCE = "0e5fde43-2de7-4fb4-833d-c7bca3b658b0"
DEMAND_URL = "https://api.neso.energy/dataset/8f2fe0af-871c-488d-8bad-960426f24601/resource/b2bde559-3455-4021-b179-dfe60c0337b0/download/demanddata_2025.csv"
NESO_LICENSE = "https://www.neso.energy/data-portal/neso-open-licence"


def ci(year, end_date, refresh):
    from_utc = f"{year}-01-01T00:00:00Z"
    end = parse_utc(end_date+"T00:00:00Z") + timedelta(days=1)
    if year == 2025:
        end = parse_utc("2026-01-01T00:00:00Z")
        # CKAN lacks interval ends: independently establish timestamp semantics.
        cross_url="https://api.carbonintensity.org.uk/intensity/2025-01-01T00:00Z/2025-01-01T01:00Z"
        cross_body,cross_meta=fetch(cross_url,RAW/"neso_ci_api_crosscheck.json",refresh=refresh)
        cross=json.loads(cross_body)["data"]
    else:
        # Do not count current-day future forecasts as historical YTD outcomes.
        retrieval=datetime.now(UTC)
        completed=retrieval.replace(minute=(retrieval.minute//30)*30,second=0,microsecond=0)
        end=min(end,completed)
    sql = (f'SELECT datetime, forecast, actual, "index" FROM "{RESOURCE}" '
           f"WHERE datetime >= '{from_utc[:-1]}' AND datetime < '{utc_text(end)[:-1]}' ORDER BY datetime LIMIT 20000")
    url = "https://api.neso.energy/api/3/action/datastore_search_sql?" + urllib.parse.urlencode({"sql":sql})
    source_id = f"neso-national-ci-{year}"
    path = RAW / f"neso_ci_{year}.json"
    try:
        body, meta = fetch(url, path, refresh=refresh)
        data = json.loads(body)
        if not data.get("success") or not isinstance(data.get("result",{}).get("records"), list):
            raise ValueError("NESO CKAN schema changed: success/result/records missing")
        raw_rows = data["result"]["records"]
        if len(raw_rows) >= 20000:
            raise ValueError("Query hit limit; pagination required")
        rows = []
        for r in raw_rows:
            start = parse_utc(r["datetime"], allow_naive=True)
            rows.append({"start_utc":utc_text(start), "end_utc":utc_text(start+timedelta(minutes=30)),
                         "grid_ci_actual_g_per_kwh":numeric(r["actual"]),
                         "grid_ci_forecast_g_per_kwh":numeric(r["forecast"]), "index":r["index"]})
        if year==2025:
            first=next(r for r in cross if parse_utc(r["from"])==parse_utc(from_utc))
            if rows[0]["grid_ci_actual_g_per_kwh"]!=first["intensity"]["actual"] or rows[0]["grid_ci_forecast_g_per_kwh"]!=first["intensity"]["forecast"]:
                raise ValueError("Portal datetime interval-start crosscheck failed; provider may have revised snapshots")
        out = PROCESSED / f"neso_ci_{year}.csv"
        write_csv(out,rows)
        record(source_id, status="verified", license="NESO Open Data Licence (portal); CC-BY-4.0 (Carbon Intensity API)",
               license_url=NESO_LICENSE, attribution="Supported by National Energy SO Open Data. National Energy System Operator / Carbon Intensity API",
               original_url=url, source_page="https://www.neso.energy/data-portal/national-carbon-intensity-forecast",
               **meta, processed_path=relative(out), processed_sha256=sha256(out), **profile(rows),
               units={"grid_ci_actual_g_per_kwh":"gCO2/kWh", "grid_ci_forecast_g_per_kwh":"gCO2/kWh"},
               provenance_status={"actual":"estimated_from_metered_generation", "forecast":"historical_forecast_issuance_unverified"},
               requested_coverage=[from_utc, utc_text(end)], client_context_date="2026-10-13",
               transformations=["Explicit UTC from portal schema; datetime is interval start crosschecked against Carbon Intensity API", "Finite numeric conversion; missing remains null", "Append half-hour exclusive end; no value imputation"],
               limitations=["National GB average intensity, not marginal or London-specific", "Forecast issue timestamp absent; not point-in-time archive", "Historical values can be revised"],
               access_limitations="Public CKAN read; two selected-year queries, 250ms inter-request throttle, cache and bounded retry")
    except Exception as exc:
        record(source_id,status="failed",original_url=url,error=str(exc),license_url=NESO_LICENSE)
        raise


def demand(refresh):
    source_id = "neso-demand-2025"
    path = RAW / "neso_demand_2025.csv"
    try:
        body, meta = fetch(DEMAND_URL,path,refresh=refresh)
        source_rows = csv_rows(path)
        required = {"SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND", "EMBEDDED_WIND_GENERATION", "EMBEDDED_SOLAR_GENERATION"}
        if not source_rows or not required <= set(source_rows[0]):
            raise ValueError(f"NESO demand schema missing required columns: {required}")
        rows = []
        counts = {}
        for r in source_rows:
            # Published 2025 file uses YYYY-MM-DD; fail if format changes.
            a,b,slots = settlement_interval(r["SETTLEMENT_DATE"],r["SETTLEMENT_PERIOD"])
            counts[r["SETTLEMENT_DATE"]] = counts.get(r["SETTLEMENT_DATE"],0)+1
            rows.append({"start_utc":utc_text(a), "end_utc":utc_text(b),
                         "settlement_date":r["SETTLEMENT_DATE"], "settlement_period":int(r["SETTLEMENT_PERIOD"]),
                         "grid_demand_mw":numeric(r["ND"]), "embedded_wind_generation_mw":numeric(r["EMBEDDED_WIND_GENERATION"]),
                         "embedded_solar_generation_mw":numeric(r["EMBEDDED_SOLAR_GENERATION"])})
        rows.sort(key=lambda r:r["start_utc"])
        out = PROCESSED / "neso_demand_2025.csv"
        write_csv(out,rows)
        record(source_id,status="verified",license="NESO Open Data Licence",license_url=NESO_LICENSE,
               attribution="Supported by National Energy SO Open Data. National Energy System Operator, Historic Demand Data",original_url=DEMAND_URL,
               source_page="https://www.neso.energy/data-portal/historic-demand-data",**meta,
               processed_path=relative(out),processed_sha256=sha256(out),**profile(rows),
               raw_columns=list(source_rows[0]),units={"grid_demand_mw":"MW","embedded_wind_generation_mw":"MW","embedded_solar_generation_mw":"MW"},
               provenance_status="observed_grid_context_revisable", settlement_day_counts={d:c for d,c in counts.items() if c!=48},
               transformations=["London midnight converted to UTC then half-hour period offsets; 46/48/50 slots", "ND is national demand; embedded wind/solar not total generation", "Sort ascending UTC; no imputation"],
               limitations=["Provider reports quality issues", "21-day publication delay and retrospective demand/solar corrections", "Context only; future observed demand excluded from decision features"])
    except Exception as exc:
        record(source_id,status="failed",original_url=DEMAND_URL,error=str(exc),license_url=NESO_LICENSE)
        raise


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--year",type=int,choices=[2025,2026],default=2025)
    p.add_argument("--through",default="2026-10-13",help="Inclusive client-context YTD cutoff; actual coverage is profiled")
    p.add_argument("--refresh",action="store_true")
    p.add_argument("--ci-only",action="store_true")
    args=p.parse_args()
    ci(args.year,args.through,args.refresh)
    if args.year==2025 and not args.ci_only:
        demand(args.refresh)
