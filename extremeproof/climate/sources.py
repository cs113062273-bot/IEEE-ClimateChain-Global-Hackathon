"""Load pinned raw files into daily series, with quality control that explains itself.

GHCN-Daily access CSV: values are tenths of a unit (TMAX in 0.1 degC, PRCP in
0.1 mm); ``<ELEMENT>_ATTRIBUTES`` is "measurement,quality,source[,time]".
Open-Meteo archive JSON: daily arrays in degC / mm, dates in the requested
local time zone.

Every value that is dropped is reported with a reason, so the verifier and the
UI can show exactly what was excluded and why.
"""
import csv
import io
import json
from datetime import date

# Gross physical limits for daily maximum temperature (degC). Wider than any
# observed national record, so they only remove obviously broken values.
TMAX_LIMITS = (-50.0, 60.0)
# A sensor reporting the same value this many days in a row is treated as stuck.
STUCK_RUN = 10


def parse_date(s):
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def load_ghcn(path, element="TMAX"):
    """Return (series, exclusions) for one element of a GHCN-Daily station CSV."""
    with open(path, newline="", encoding="utf-8") as f:
        return parse_ghcn(f.read(), element)


def parse_ghcn(text, element="TMAX"):
    """``text`` is one CSV, or a list of CSVs (pinned history, then the season fetch) checked as one record."""
    texts = [text] if isinstance(text, str) else text
    rows = (row for t in texts for row in csv.DictReader(io.StringIO(t, newline="")))
    series, exclusions, seen = {}, [], set()
    for row in rows:
        raw = (row.get(element) or "").strip()
        if not raw:
            continue
        d = parse_date(row["DATE"])
        attrs = (row.get(element + "_ATTRIBUTES") or "").split(",")
        qflag = attrs[1].strip() if len(attrs) > 1 else ""
        value = int(raw) / 10.0
        if d in seen:
            exclusions.append({"date": d.isoformat(), "value": value, "reason": "duplicate_date"})
            series.pop(d, None)
            continue
        seen.add(d)
        if qflag:
            exclusions.append({"date": d.isoformat(), "value": value, "reason": f"ghcn_quality_flag_{qflag}"})
            continue
        if element == "TMAX" and not (TMAX_LIMITS[0] <= value <= TMAX_LIMITS[1]):
            exclusions.append({"date": d.isoformat(), "value": value, "reason": "outside_physical_limits"})
            continue
        series[d] = value
    exclusions += _drop_stuck(series)
    exclusions.sort(key=lambda e: e["date"])
    return series, exclusions


def _drop_stuck(series):
    """Remove runs of >= STUCK_RUN consecutive days with an identical value."""
    out = []
    days = sorted(series)
    i = 0
    while i < len(days):
        j = i
        while (j + 1 < len(days) and (days[j + 1] - days[j]).days == 1
               and series[days[j + 1]] == series[days[i]]):
            j += 1
        if j - i + 1 >= STUCK_RUN:
            for d in days[i:j + 1]:
                out.append({"date": d.isoformat(), "value": series.pop(d), "reason": "stuck_value_run"})
        i = j + 1
    return out


def load_open_meteo(path, variable="temperature_2m_max"):
    with open(path, encoding="utf-8") as f:
        return parse_open_meteo(f.read(), variable)


def parse_open_meteo(text, variable="temperature_2m_max"):
    texts = [text] if isinstance(text, str) else text
    out = {}
    for t_ in texts:
        doc = json.loads(t_)
        daily = doc["daily"]
        for t, v in zip(daily["time"], daily[variable]):
            if v is not None:
                out[parse_date(t)] = float(v)
    meta = {k: doc.get(k) for k in ("latitude", "longitude", "elevation", "timezone", "utc_offset_seconds")}
    meta["units"] = doc.get("daily_units", {}).get(variable)
    return out, meta


def load_stations(path, ids=None):
    """Parse ghcnd-stations.txt fixed-width rows -> {id: {name, lat, lon, elev}}."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            sid = line[0:11]
            if ids is not None and sid not in ids:
                continue
            out[sid] = {"lat": float(line[12:20]), "lon": float(line[21:30]),
                        "elev": float(line[31:37]), "name": line[41:71].strip()}
    return out
