"""Real workplace charging sessions, normalised to UTC half-hour slots.

Source: de Bont et al. (2025), 4TU.ResearchData, doi:10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2
(CC BY-NC-SA 4.0). The licence asks users to consult the authors before
redistributing transformed data, so raw and session-level derived rows stay in
gitignored data/raw and data/processed. Only aggregate results are committed.

Times in the source are Europe/Amsterdam local wall-clock. All slots here are UTC.
"""
from __future__ import annotations
import hashlib
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data/raw/workplace_sessions_utrecht/202410DatasetEVOfficeParking_v0.csv"
SOURCE = {
    "source_id": "utrecht-workplace-ev-sessions",
    "title": "Electric Vehicle Charging Session Data of Large Office Parking Lot (v2)",
    "doi": "10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2",
    "licence": "CC BY-NC-SA 4.0",
    "attribution": "de Bont, Hoogsteen, Hurink, Kokhuis, Kusche et al. (2025), 4TU.ResearchData",
    "role": "Driver arrival, departure and energy behaviour. Combined with GB grid records as a constructed scenario.",
}
# README: charging IDs shared during roll-out cannot be attributed to one driver.
SHARED_IDS = {"EV107", "EV191", "EV132", "EV148", "EV342", "EV242", "EV130", "EV173", "EV131", "EV384",
              "EV318", "EV127", "EV257", "EV192", "EV129", "EV211", "EV323", "EV343", "EV161", "EV456"}
# Rails E and M share one transformer connection (README); used as one constrained site.
SITE_RAILS = ("E", "M")
SLOT = pd.Timedelta(minutes=30)
# Chronological split fixed before any test-period evaluation (protocol.json).
SPLITS = {"train": ("2021-01-01", "2023-01-01"), "validation": ("2023-01-01", "2024-01-01"),
          "test": ("2024-01-01", "2024-10-03")}
# Each session day is replayed on the GB grid day with the same weekday:
# 2023 + 728 days, 2024 + 364 days. Grid days need seven prior days for forecasts.
GRID_SHIFT_DAYS = {2023: 728, 2024: 364}
GRID_FIRST, GRID_LAST = pd.Timestamp("2025-01-08"), pd.Timestamp("2025-12-31")


def available():
    return RAW.exists()


def raw_sha256():
    return hashlib.sha256(RAW.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load_sessions():
    """All sessions with UTC times, never silently dropping rows: exclusions are counted."""
    if not RAW.exists():
        raise ValueError("Workplace session data missing. Run scripts/fetch_workplace_sessions.py (public, no account).")
    df = pd.read_csv(RAW, sep=";", encoding="utf-8-sig")
    quality = {"raw_rows": int(len(df))}
    for column in ("start_datetime", "end_datetime"):
        local = pd.to_datetime(df[column])
        df[column.replace("datetime", "utc")] = local.dt.tz_localize(
            "Europe/Amsterdam", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC")
    bad_time = df.start_utc.isna() | df.end_utc.isna()
    crosses = df.start_utc.dt.floor("D") != (df.end_utc - pd.Timedelta(seconds=1)).dt.floor("D")
    quality.update(ambiguous_local_time=int(bad_time.sum()), crosses_utc_midnight=int((crosses & ~bad_time).sum()))
    df = df.loc[~bad_time & ~crosses].copy()
    df["driver"] = np.where(df.EV_id_x.isin(SHARED_IDS), "shared", df.EV_id_x)
    df["energy_kwh"] = df.total_energy.astype(float)
    df["dwell_h"] = (df.end_utc - df.start_utc).dt.total_seconds() / 3600
    df["date"] = df.start_utc.dt.strftime("%Y-%m-%d")
    day = df.start_utc.dt.floor("D")
    df["arrival_h"] = (df.start_utc - day).dt.total_seconds() / 3600
    df["departure_h"] = (df.end_utc - day).dt.total_seconds() / 3600
    df["weekday"] = df.start_utc.dt.weekday
    df["site"] = df.rail.isin(SITE_RAILS)
    df = df.sort_values(["start_utc", "EV_id_x"]).reset_index(drop=True)
    df["session_id"] = [hashlib.sha256(f"{a}|{b}|{c}".encode()).hexdigest()[:12]
                        for a, b, c in zip(df.EV_id_x, df.start_utc, df.evse_uid)]
    quality["usable_rows"] = int(len(df))
    quality["shared_id_rows"] = int((df.driver == "shared").sum())
    quality["site_rows"] = int(df.site.sum())
    return df, quality


def split_of(date):
    for name, (start, end) in SPLITS.items():
        if start <= date < end:
            return name
    return None


def grid_date(date):
    """Same-weekday GB grid day for a session day, or None outside pinned 2025 data."""
    d = pd.Timestamp(date)
    shift = GRID_SHIFT_DAYS.get(d.year)
    if shift is None:
        return None
    mapped = d + pd.Timedelta(days=shift)
    return mapped.strftime("%Y-%m-%d") if GRID_FIRST <= mapped <= GRID_LAST and mapped.weekday() == d.weekday() else None


def site_days(split, excluded=None):
    """Weekday site days in a split with a complete mapped GB grid day.

    Pass a list as `excluded` to receive (date, reason) for every dropped day.
    """
    from .grid import grid_complete
    df, _ = load_sessions()
    start, end = SPLITS[split]
    rows = df.loc[df.site & (df.date >= start) & (df.date < end) & (df.weekday < 5)]
    days = []
    for date, group in rows.groupby("date"):
        mapped = grid_date(date)
        reason = ("no mapped 2025 grid day" if not mapped else "fewer than 3 sessions" if len(group) < 3
                  else "incomplete grid outcomes" if not grid_complete(mapped) else None)
        if reason is None:
            days.append(date)
        elif excluded is not None:
            excluded.append((date, reason))
    return days


def day_sessions(date):
    df, _ = load_sessions()
    return df.loc[df.site & (df.date == date)].reset_index(drop=True)
