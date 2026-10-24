"""Precompute what the web app shows, from the pinned raw files and the engine.

Writes web/public/data/<site>.json. For every year 1966-2026 and every rule
variant (data source x gap filling x base period x percentile) it stores the
longest June-September spell above the threshold; for years inside the base
period it stores the 29 bootstrap replicates instead (Zhang et al. 2005), so the
browser can apply any minimum spell length exactly. Gap-filling for year Y is
fitted only on data up to the end of Y-1, as an agreement would require.

    extremeproof/.venv/Scripts/python -m extremeproof.scripts.build_web_data [site ...]
"""
import json
from datetime import date
from pathlib import Path

from extremeproof.climate import engine as E
from extremeproof.climate import fill as F
from extremeproof.climate.sources import load_ghcn, load_open_meteo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "data"
SITES = {
    "antalya": {"name": "Antalya", "station": "TUM00017300",
                "blurb": "COP31 host city. The station's recent summers are mostly missing."},
    "mugla": {"name": "Muğla", "station": "TUM00017292",
              "blurb": "Complete recent record: a control where the data are not the problem."},
    # The other pinned GHCN stations in southern and western Türkiye, for the regional scan.
    "izmir": {"name": "İzmir", "station": "TUM00017220", "blurb": "Aegean coast."},
    "finike": {"name": "Finike", "station": "TU000017375", "blurb": "Mediterranean coast, west of Antalya."},
    "isparta": {"name": "Isparta", "station": "TU000017240", "blurb": "Lake district, about 1,000 m."},
    "afyon": {"name": "Afyon", "station": "TUM00017190", "blurb": "Inland plateau, about 1,000 m."},
    "konya": {"name": "Konya", "station": "TUM00017244", "blurb": "Central Anatolian plateau, about 1,000 m."},
    "mersin": {"name": "Mersin", "station": "TUM00017340", "blurb": "Mediterranean coast."},
    "adana": {"name": "Adana", "station": "TUW00033308", "blurb": "Çukurova plain."},
    "iskenderun": {"name": "İskenderun", "station": "TUM00017370", "blurb": "Eastern Mediterranean coast."},
    # The same engine outside Türkiye, for the regional scan.
    "athens": {"name": "Athens", "station": "GR000016716", "blurb": "Greece. The Hellenic Red Cross released heatwave relief by a threshold in 2024."},
    "larissa": {"name": "Larissa", "station": "GR000016648", "blurb": "Thessaly plain, Greece's main farming plain."},
    "bucharest": {"name": "Bucharest", "station": "ROE00108889", "blurb": "Romania, Bucharest-Băneasa."},
    "sofia": {"name": "Sofia", "station": "BUM00015614", "blurb": "Bulgaria, about 530 m."},
}
BASES = {"1961-1990": (date(1961, 1, 1), date(1990, 12, 31)), "1991-2020": (date(1991, 1, 1), date(2020, 12, 31))}
PERCENTILES = (90, 95)
SEASON = ((6, 1), (9, 30))
SEASON_DOYS = (152, 274)
YEARS = range(1966, 2027)
FIRST = date(1963, 1, 1)
LAST = date(2026, 9, 30)
VARIANTS = {  # id -> (source, fill method)
    "era5": ("era5", "none"),
    "station": ("station", "none"),
    "station_qm": ("station", "era5_quantile_map"),
    "station_linear": ("station", "era5_monthly_linear"),
    "station_raw": ("station", "era5_raw"),
}


def r1(x):
    return None if x is None else round(x, 2)


def build(site_id):
    info = SITES[site_id]
    sid = info["station"]
    station, excluded = load_ghcn(ROOT / "data" / "raw" / "ghcn" / f"{sid}.csv")
    era5, meta = load_open_meteo(ROOT / "data" / "raw" / "era5" / f"{sid}_era5.json")
    stations = json.loads((ROOT / "data" / "stations.json").read_text(encoding="utf-8"))["stations"]
    src = {"station": station, "era5": era5}

    days = list(E.daterange(FIRST, LAST))
    out = {
        "site": {"id": site_id, **info},
        "station": {"id": sid, "lat": stations[sid]["lat"], "lon": stations[sid]["lon"], "elev_m": stations[sid]["elev_m"],
                    "qc_excluded": len(excluded)},
        "era5_grid": {"lat": meta["latitude"], "lon": meta["longitude"], "elev_m": meta["elevation"]},
        "series": {"start": FIRST.isoformat(), "station": [r1(station.get(d)) for d in days], "era5": [r1(era5.get(d)) for d in days]},
        "coverage": {s: {b: E.completeness(src[s], *bb)[0] * 1000 // E.completeness(src[s], *bb)[1] for b, bb in BASES.items()}
                     for s in src},
        "thresholds": {},
        "backtest": {},
        "years": list(YEARS),
        "notes": {
            "fill": "Gap filling for year Y is fitted on paired station/ERA5 days from 1963 to the end of Y-1.",
            "bootstrap": "Years inside the base period carry 29 bootstrap replicates (Zhang et al. 2005); "
                         "a year counts as triggered when at least half of them trigger.",
        },
    }
    # full-year thresholds for the charts (index = day of year - 1)
    for s in src:
        for b, (b0, b1) in BASES.items():
            for pct in PERCENTILES:
                th = E.percentile_doy(src[s], b0, b1, pct)
                out["thresholds"][f"{s}|{b}|{pct}"] = [r1(th.get(k)) for k in range(1, 367)]

    fills = {}
    for y in YEARS:
        for m in ("era5_quantile_map", "era5_monthly_linear"):
            try:
                fills[(m, y)] = F.fit(m, station, era5, FIRST, date(y - 1, 12, 31))
            except ValueError:  # too little paired history yet: the gaps stay unfilled
                fills[(m, y)] = {"method": "none"}
        fills[("era5_raw", y)] = {"method": "era5_raw"}
        fills[("none", y)] = {"method": "none"}

    for base, (b0, b1) in BASES.items():
        for pct in PERCENTILES:
            for s in src:
                series = src[s]
                th = E.percentile_doy(series, b0, b1, pct, doy_range=SEASON_DOYS)
                reps = {}
                for y in YEARS:
                    if E.in_base(y, b0, b1):
                        reps[y] = [E.percentile_doy(E.replace_year(series, y, o), b0, b1, pct, doy_range=SEASON_DOYS)
                                   for o in range(b0.year, b1.year + 1) if o != y]
                for vid, (vs, method) in VARIANTS.items():
                    if vs != s:
                        continue
                    table = {}
                    for y in YEARS:
                        season = E.season_dates(y, SEASON)
                        vals, missing, filled = {}, 0, 0
                        for d in season:
                            v = series.get(d)
                            if v is None and method != "none":
                                v = F.predict(fills[(method, y)], d, era5.get(d))
                                filled += v is not None
                            missing += v is None
                            if v is not None:
                                vals[d] = v
                        row = {"missing": missing, "filled": filled}
                        if y in reps:
                            row["reps"] = [E.longest_spell(vals, t, y, SEASON) for t in reps[y]]
                        else:
                            row["longest"] = E.longest_spell(vals, th, y, SEASON)
                        table[str(y)] = row
                    out["backtest"][f"{vid}|{base}|{pct}"] = table
                print(site_id, base, pct, s, "done", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{site_id}.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")


def main():
    import sys
    for s in sys.argv[1:] or SITES:
        build(s)
    print("wrote", sorted(p.name for p in OUT.glob("*.json")))


if __name__ == "__main__":
    main()
