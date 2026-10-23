"""GB grid day for the car park: pinned NESO carbon intensity + ERA5 radiation.

Formulas are the disclosed transforms in services.lineage.TRANSFORM_CONFIG. The
decision-time carbon forecast is the past-only seven-day seasonal median: the
LightGBM carbon model showed no resolved carbon value and is not used here.
"""
from __future__ import annotations
import json
from functools import lru_cache
import numpy as np
import pandas as pd
from backend.app.services.lineage import ANCHORS_PATH, _trusted_bytes
from backend.app.ml.forecast import seasonal

T = 48
DT = .5


@lru_cache(maxsize=1)
def pinned_frame():
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    carbon = json.loads(_trusted_bytes(anchors["sources"]["neso-national-ci-2025"]))
    weather = json.loads(_trusted_bytes(anchors["sources"]["openmeteo-london-weather-2025"]))["hourly"]
    radiation = dict(zip(pd.to_datetime(weather["time"], utc=True), weather["shortwave_radiation"]))
    rows = []
    for row in carbon["result"]["records"]:
        start = pd.Timestamp(row["datetime"], tz="UTC")
        rows.append({"start_utc": start, "grid_ci_actual_g_per_kwh": float(row["actual"]) if row["actual"] is not None else np.nan,
                     "shortwave_radiation_w_per_m2": radiation.get(start.floor("h") + pd.Timedelta(hours=1), np.nan)})
    return pd.DataFrame(rows).set_index("start_utc").sort_index(), {k: anchors["sources"][k]["sha256"] for k in anchors["sources"]}


def base_load_kwh(scale=1.0):
    hours = (np.arange(T) + .5) * DT
    return scale * .5 * (6 + 8 * ((8 <= hours) & (hours < 18)) + 2 * ((18 <= hours) & (hours < 22)))


def tariff():
    hours = (np.arange(T) + .5) * DT
    return np.where(hours < 7, .12, np.where((16 <= hours) & (hours < 20), .36, .23))


def calendar_pv(date, kwp):
    day = pd.Timestamp(date).dayofyear
    daylight = 12 + 4 * np.sin(2 * np.pi * (day - 80) / 365); sunrise = 12 - daylight / 2
    season = .58 + .20 * np.sin(2 * np.pi * (day - 80) / 365)
    hours = (np.arange(T) + .5) * DT
    inside = (sunrise <= hours) & (hours <= sunrise + daylight)
    return np.where(inside, kwp * .5 * season * np.maximum(0, np.sin(np.pi * (hours - sunrise) / daylight)), 0.)


def grid_complete(date):
    frame, _ = pinned_frame()
    issue = pd.Timestamp(date, tz="UTC")
    day = frame.loc[(frame.index >= issue) & (frame.index < issue + pd.Timedelta(days=1))]
    return len(day) == T and not day.grid_ci_actual_g_per_kwh.isna().any() and not day.shortwave_radiation_w_per_m2.isna().any()


def grid_day(date, solar_kwp=20.0):
    """Decision inputs (forecasts) and outcomes (actuals) kept in separate keys."""
    frame, anchors = pinned_frame()
    issue = pd.Timestamp(date, tz="UTC")
    day = frame.loc[(frame.index >= issue) & (frame.index < issue + pd.Timedelta(days=1))]
    if len(day) != T or day.grid_ci_actual_g_per_kwh.isna().any() or day.shortwave_radiation_w_per_m2.isna().any():
        raise ValueError(f"Grid day {date} lacks 48 complete carbon/radiation outcomes")
    past = frame.loc[frame.index < issue]
    if past.empty:
        raise ValueError("No past carbon observations before decision midnight")
    radiation = day.shortwave_radiation_w_per_m2.to_numpy(dtype=float)
    return {
        "date": date,
        "start_utc": [ts.isoformat().replace("+00:00", "Z") for ts in day.index],
        "ci_forecast": np.clip(seasonal(past, issue), 0, 1500),
        "ci_actual": day.grid_ci_actual_g_per_kwh.to_numpy(dtype=float),
        "tariff": tariff(),
        "base_load": base_load_kwh(),
        "pv_forecast": calendar_pv(date, solar_kwp),
        "pv_outcome": solar_kwp * .5 * .8 * np.clip(radiation / 1000, 0, 1),
        "source_sha256": anchors,
        "forecast_method": "past-only-seven-day-seasonal-median-v1",
    }
