"""Download and pin the raw climate data ExtremeProof uses.

Every file is recorded in data/manifest.json with its URL, retrieval time,
SHA-256 and licence, so the demo and the verifier can run fully offline.
Existing files are never re-downloaded unless --refresh is given.

Run from the repository root:  python -m extremeproof.scripts.fetch_data
"""
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"
UA = "ExtremeProof/0.1 (IEEE ClimateChain hackathon research prototype)"

# Station id -> display name. Antalya is the demo site; the others are neighbours
# used for gap filling and as a complete-record control (Mugla).
STATIONS = {
    "TUM00017300": "Antalya",
    "TU000017375": "Finike",
    "TU000017240": "Isparta",
    "TUM00017292": "Mugla",
    "TUM00017340": "Mersin",
    # Additional long-record stations in southern/western Turkiye, used only to
    # evaluate gap filling with whole stations held out.
    "TUM00017220": "Izmir",
    "TUW00033308": "Adana",
    "TUM00017370": "Iskenderun",
    "TUM00017244": "Konya",
    "TUM00017190": "Afyon",
}
# The same rule outside Türkiye. Greece, Romania and Bulgaria keep summer time at
# UTC+3, so the season day is the same local day as in Türkiye. ERA5 only (no
# ERA5-Land): these stations are not part of the gap-filling evaluation.
ABROAD = {
    "GR000016716": "Athens",
    "GR000016648": "Larissa",
    "ROE00108889": "Bucharest",
    "BUM00015614": "Sofia",
}
ALL_STATIONS = {**STATIONS, **ABROAD}

GHCN_URL = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{}.csv"
GHCN_STATIONS_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
GHCN_INVENTORY_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt"
GHCN_LICENCE = {
    "licence": "No explicit licence published; NOAA/NCEI asks for citation (doi:10.7289/V5D21VHZ). "
               "Readme and ISO metadata state no use restrictions; electronic downloads are free.",
    "licence_url": "https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.ncdc:C00861",
    "citation": "Menne, M.J. et al. (2012): Global Historical Climatology Network - Daily (GHCN-Daily), "
                "Version 3. NOAA National Climatic Data Center. doi:10.7289/V5D21VHZ",
}

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
ERA5_START, ERA5_END = "1950-01-01", "2026-09-30"
ERA5_MODELS = ("era5", "era5_land")
OPEN_METEO_LICENCE = {
    "licence": "CC BY 4.0 (Open-Meteo API data); free API is for non-commercial use only, "
               "<10,000 calls/day. Underlying reanalysis: Copernicus Climate Change Service (C3S) / ECMWF.",
    "licence_url": "https://open-meteo.com/en/licence",
    "terms_url": "https://open-meteo.com/en/terms",
    "citation": "Weather data by Open-Meteo.com (https://open-meteo.com/); Hersbach et al. (2020) ERA5; "
                "Munoz Sabater (2019) ERA5-Land; Copernicus Climate Change Service.",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, refresh):
    if dest.exists() and not refresh:
        return False
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(30):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            break
        except urllib.error.HTTPError as e:
            # Open-Meteo weights long date ranges as many calls; back off on 429.
            # The minute limit clears quickly, the hourly one needs a longer wait.
            if e.code != 429 or attempt == 29:
                raise
            reason = e.read().decode("utf-8", "replace")
            wait = 600 if "Hourly" in reason or "Daily" in reason else 65
            print(f"  rate limited ({reason.strip()[:80]}), waiting {wait}s", flush=True)
            time.sleep(wait)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return True


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"schema": "extremeproof.manifest.v1", "files": {}}


def pin(manifest, dest, url, refreshed, **extra):
    key = dest.relative_to(ROOT).as_posix()
    old = manifest["files"].get(key, {})
    retrieved = old.get("retrieved_utc") if not refreshed and old else None
    if retrieved is None:
        # The file was just written by download(), or cached before a manifest existed.
        retrieved = datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["files"][key] = {
        "url": url,
        "retrieved_utc": retrieved,
        "sha256": sha256(dest),
        "bytes": dest.stat().st_size,
        **extra,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()
    manifest = load_manifest()

    for name, url in (("ghcnd-stations.txt", GHCN_STATIONS_URL), ("ghcnd-inventory.txt", GHCN_INVENTORY_URL)):
        dest = RAW / "ghcn" / name
        got = download(url, dest, args.refresh)
        pin(manifest, dest, url, got, source="GHCN-Daily station metadata", **GHCN_LICENCE)

    for sid, label in ALL_STATIONS.items():
        url = GHCN_URL.format(sid)
        dest = RAW / "ghcn" / f"{sid}.csv"
        got = download(url, dest, args.refresh)
        pin(manifest, dest, url, got, source="GHCN-Daily", station=sid, station_name=label, **GHCN_LICENCE)
        save(manifest)
        print(f"GHCN {sid} {label}: {'downloaded' if got else 'cached'}")

    coords = station_coords(RAW / "ghcn" / "ghcnd-stations.txt")
    write_station_subset(RAW / "ghcn" / "ghcnd-stations.txt", RAW / "ghcn" / "ghcnd-inventory.txt")
    for sid, label in ALL_STATIONS.items():
        lat, lon = coords[sid]
        for model in ERA5_MODELS if sid in STATIONS else ("era5",):
            params = {
                "latitude": lat, "longitude": lon, "start_date": ERA5_START, "end_date": ERA5_END,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "timezone": "Europe/Istanbul", "models": model,
            }
            url = OPEN_METEO_URL + "?" + urllib.parse.urlencode(params)
            dest = RAW / "era5" / f"{sid}_{model}.json"
            got = download(url, dest, args.refresh)
            pin(manifest, dest, url, got, source=f"Open-Meteo historical API, model={model}",
                station=sid, station_name=label, **OPEN_METEO_LICENCE)
            save(manifest)
            print(f"{model} {sid} {label}: {'downloaded' if got else 'cached'}")
            if got:
                time.sleep(90)

    save(manifest)
    print(f"pinned {len(manifest['files'])} files -> {MANIFEST.relative_to(ROOT)}")


def save(manifest):
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def write_station_subset(stations_path, inventory_path):
    """Small committed copy of the station metadata the demo needs (the full index files are gitignored)."""
    out = {}
    for line in stations_path.read_text(encoding="utf-8").splitlines():
        sid = line[0:11]
        if sid in ALL_STATIONS:
            out[sid] = {"name": ALL_STATIONS[sid], "ghcn_name": line[41:71].strip(), "lat": float(line[12:20]),
                        "lon": float(line[21:30]), "elev_m": float(line[31:37]), "inventory": {}}
    for line in inventory_path.read_text(encoding="utf-8").splitlines():
        sid = line[0:11]
        if sid in out:
            out[sid]["inventory"][line[31:35]] = [int(line[36:40]), int(line[41:45])]
    dest = ROOT / "data" / "stations.json"
    dest.write_text(json.dumps({
        "source": [GHCN_STATIONS_URL, GHCN_INVENTORY_URL],
        "note": "Subset of ghcnd-stations.txt and ghcnd-inventory.txt; see manifest.json for the pinned hashes of the full files.",
        "stations": out}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def station_coords(path):
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        sid = line[0:11]
        if sid in ALL_STATIONS:
            out[sid] = (float(line[12:20]), float(line[21:30]))
    missing = set(ALL_STATIONS) - set(out)
    if missing:
        raise SystemExit(f"stations missing from ghcnd-stations.txt: {sorted(missing)}")
    return out


if __name__ == "__main__":
    main()
