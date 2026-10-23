"""What can be pinned at signing, and the season data that only exists afterwards.

A spec is signed before the season, so it can pin only data that exist then:
each source's archive up to 31 December of the previous year. Both the base
period and the gap-fill fit period end there. The season's observations do not
exist at signing; the spec names where they will be fetched from, and each
provider fetches them after the season and binds their sha256 to its on-chain
report through the evidence digest.

In this prototype both halves are cut from one pinned download made in October
2026 (``data/raw``, hashes in ``data/manifest.json``):

* ``history_bytes`` keeps the header and every row dated before 1 January of
  the observation year, byte for byte as in that download;
* ``fetch_season`` stands in for the publisher: it returns the season rows of
  the same download, as a provider would get them after the season.

A real deployment pins the file downloaded at signing and fetches the season
from the publisher. Revisions the publisher makes between the two dates, and
publication delay, are not modelled.

With ``EP_LIVE_FETCH=1`` the providers fetch the season from the publisher
itself (the URL the spec names: NOAA NCEI or Open-Meteo) instead of cutting it
from the pinned download; the history half is always the pinned file.
"""
import json
import os
import urllib.request
from datetime import date

GHCN_URL = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{station}.csv"
OPEN_METEO_URL = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start}"
                  "&end_date={end}&daily=temperature_2m_max&timezone=Europe%2FIstanbul&models=era5")
PUBLISHERS = {"ghcn_daily": "NOAA NCEI GHCN-Daily", "open_meteo": "Open-Meteo historical API (ERA5)"}
EXT = {"ghcn_daily": "csv", "open_meteo": "json"}


def raw_file(kind, station):
    return f"data/raw/ghcn/{station}.csv" if kind == "ghcn_daily" else f"data/raw/era5/{station}_era5.json"


def history_name(kind, station, year):
    """Logical name of the archive the parties pin for observation year ``year``."""
    return f"history/{station}_{'ghcn' if kind == 'ghcn_daily' else 'era5'}_to_{year - 1}.{EXT[kind]}"


def season_name(kind, station, year):
    return f"{station}_{'ghcn' if kind == 'ghcn_daily' else 'era5'}_{year}.{EXT[kind]}"


def season_url(kind, station, start, end, grid=None):
    if kind == "ghcn_daily":
        return GHCN_URL.format(station=station)
    return OPEN_METEO_URL.format(lat=grid[0], lon=grid[1], start=start, end=end)


def _day(s):
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def slice_ghcn(raw, first=None, last=None):
    """Header plus the rows dated first..last (inclusive; None = open), bytes unchanged."""
    lines = raw.splitlines(keepends=True)
    keep = [lines[0]]
    for line in lines[1:]:
        d = _day(line.split(b",", 2)[1].strip(b'"').decode("ascii"))
        if (first is None or d >= first) and (last is None or d <= last):
            keep.append(line)
    return b"".join(keep)


def slice_open_meteo(raw, first=None, last=None):
    doc = json.loads(raw)
    daily = doc["daily"]
    idx = [i for i, t in enumerate(daily["time"]) if (first is None or _day(t) >= first) and (last is None or _day(t) <= last)]
    doc["daily"] = {k: [v[i] for i in idx] for k, v in daily.items()}
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def cut(kind, raw, first=None, last=None):
    return (slice_ghcn if kind == "ghcn_daily" else slice_open_meteo)(raw, first, last)


def history_bytes(root, kind, station, year):
    raw = (root / raw_file(kind, station)).read_bytes()
    return cut(kind, raw, None, date(year - 1, 12, 31))


def download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "extremeproof-provider"})
    with urllib.request.urlopen(req, timeout=180) as f:
        return f.read()


def fetch_season(root, src, year, through=None):
    """What a provider gets from the publisher: the observation year up to the season end, or during the
    season up to ``through``, the last day already published. Simulated from the pinned download unless
    EP_LIVE_FETCH=1, which downloads the URL the spec names."""
    sd = src["season_data"]
    if os.environ.get("EP_LIVE_FETCH") == "1":
        raw = download(sd["url"])
    else:
        raw = (root / raw_file(src["kind"], src["station"])).read_bytes()
    last = _day(sd["to"]) if through is None else min(_day(sd["to"]), through)
    return cut(src["kind"], raw, _day(sd["from"]), last)


def read_logical(root, name):
    """Bytes of a pinned logical file: ``history/...`` is derived from data/raw, anything else is read as is."""
    if name.startswith("history/"):
        stem = name.split("/", 1)[1].rsplit(".", 1)[0]  # TUM00017292_ghcn_to_2020
        station, kind, _, last = stem.split("_")
        return history_bytes(root, "ghcn_daily" if kind == "ghcn" else "open_meteo", station, int(last) + 1)
    return (root / name).read_bytes()
