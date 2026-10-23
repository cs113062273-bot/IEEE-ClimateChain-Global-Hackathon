"""Recompute the data facts the project relies on, from pinned raw files only.

Writes extremeproof/docs/facts.json. Run from the repository root:
    python -m extremeproof.scripts.reproduce_facts
"""
import json
import math
from datetime import date
from pathlib import Path

from extremeproof.climate import engine as E
from extremeproof.climate.sources import load_ghcn, load_open_meteo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "facts.json"
ANTALYA = "TUM00017300"
NEIGHBOURS = {"TU000017375": "Finike", "TU000017240": "Isparta", "TUM00017292": "Mugla", "TUM00017340": "Mersin"}
BASES = {"1961-1990": (date(1961, 1, 1), date(1990, 12, 31)), "1991-2020": (date(1991, 1, 1), date(2020, 12, 31))}
SEASON = ((6, 1), (9, 30))
MIN_SPELL = 6
YEARS = range(1966, 2026)


def haversine_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def days_per_year(series, years):
    return {y: sum(1 for d in series if d.year == y) for y in years}


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def spell_table(series, base, bootstrap):
    """Longest Jun-Sep spell above the base-period p90, per year (bootstrapped for in-base years if asked)."""
    th = E.percentile_doy(series, *base)
    out = {}
    for y in YEARS:
        if bootstrap and E.in_base(y, *base):
            reps = E.bootstrapped(series, *base, y, lambda t: E.longest_spell(series, t, y, SEASON))
            out[y] = {"longest": sum(reps) / len(reps),
                      "triggered_share": sum(r >= MIN_SPELL for r in reps) / len(reps)}
        else:
            ls = E.longest_spell(series, th, y, SEASON)
            out[y] = {"longest": ls, "triggered_share": 1.0 if ls >= MIN_SPELL else 0.0}
    return out


def main():
    facts = {}
    stn, excl = load_ghcn(RAW / "ghcn" / f"{ANTALYA}.csv")
    era5, era5_meta = load_open_meteo(RAW / "era5" / f"{ANTALYA}_era5.json")
    first = min(stn)
    p, t = E.completeness(stn, *BASES["1961-1990"])
    p2, t2 = E.completeness(stn, *BASES["1991-2020"])
    facts["antalya_station"] = {
        "id": ANTALYA, "first_tmax_date": first.isoformat(), "last_tmax_date": max(stn).isoformat(),
        "qc_exclusions": len(excl),
        "base_1961_1990_present_days": p, "base_1961_1990_total_days": t, "base_1961_1990_share": round(p / t, 4),
        "base_1991_2020_present_days": p2, "base_1991_2020_total_days": t2, "base_1991_2020_share": round(p2 / t2, 4),
        "tmax_days_per_year_2015_2025": days_per_year(stn, range(2015, 2026)),
    }

    pairs = sorted(d for d in stn if d in era5)
    xs = [stn[d] for d in pairs]
    ys = [era5[d] for d in pairs]
    facts["antalya_station_vs_era5"] = {
        "era5_grid": era5_meta, "paired_days": len(pairs),
        "pearson_r": round(pearson(xs, ys), 4),
        "mean_era5_minus_station_degC": round(sum(ys) / len(ys) - sum(xs) / len(xs), 3),
        "jja_mean_era5_minus_station_degC": round(
            sum(era5[d] - stn[d] for d in pairs if d.month in (6, 7, 8)) / sum(1 for d in pairs if d.month in (6, 7, 8)), 3),
    }

    trig = {}
    for src_name, series in (("era5", era5), ("station", stn)):
        for bname, base in BASES.items():
            for boot in (False, True):
                key = f"{src_name}|{bname}|{'bootstrap' if boot else 'no_bootstrap'}"
                tab = spell_table(series, base, boot)
                trig[key] = {
                    "triggered_years": [y for y, v in tab.items() if v["triggered_share"] >= 0.5],
                    "longest_spell": {y: v["longest"] for y, v in tab.items()},
                    "triggered_share": {y: v["triggered_share"] for y, v in tab.items()},
                }
                print(key, trig[key]["triggered_years"])
    facts["antalya_heat_trigger"] = {
        "rule": f"Jun 1-Sep 30, at least {MIN_SPELL} consecutive days with TX above the calendar-day 90th "
                "percentile of the base period (5-day window, type-8 quantile); missing days break a spell; no gap filling. "
                "With bootstrap, in-base years count as triggered when at least half of the Zhang et al. (2005) replicates trigger.",
        "years": [YEARS.start, YEARS.stop - 1],
        "results": trig,
    }

    meta = json.loads((ROOT / "data" / "stations.json").read_text(encoding="utf-8"))["stations"]
    nb = {}
    for sid, name in NEIGHBOURS.items():
        s, ex = load_ghcn(RAW / "ghcn" / f"{sid}.csv")
        nb[sid] = {"name": name, "distance_km": round(haversine_km(meta[ANTALYA], meta[sid]), 1),
                   "qc_exclusions": len(ex), "tmax_days_per_year_2015_2025": days_per_year(s, range(2015, 2026))}
    facts["neighbours"] = nb

    inv = RAW / "ghcn" / "ghcnd-inventory.txt"
    if inv.exists():  # large index file, gitignored; fetched by scripts/fetch_data.py
        facts["mediterranean_inventory"] = inventory_count(inv)
    elif OUT.exists():
        facts["mediterranean_inventory"] = json.loads(OUT.read_text(encoding="utf-8")).get("mediterranean_inventory")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(facts, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in facts.items() if k != "antalya_heat_trigger"}, indent=2, default=str))


# Countries bordering the Mediterranean Sea, as GHCN FIPS country codes.
MED_FIPS = {"SP", "FR", "MN", "IT", "SI", "HR", "BK", "MJ", "AL", "GR", "TU", "SY", "LE", "IS", "GZ", "EG",
            "LY", "TS", "AG", "MO", "CY", "MT"}


def inventory_count(inv_path):
    """Stations whose TMAX inventory spans 1961-2024, for Mediterranean-coast countries.

    The inventory only lists first and last year with any data; completeness
    must still be checked station by station.
    """
    by_country, total = {}, 0
    with open(inv_path, encoding="utf-8") as f:
        for line in f:
            sid, elem, y0, y1 = line[0:11], line[31:35], int(line[36:40]), int(line[41:45])
            if elem == "TMAX" and sid[:2] in MED_FIPS and y0 <= 1961 and y1 >= 2024:
                by_country[sid[:2]] = by_country.get(sid[:2], 0) + 1
                total += 1
    return {"definition": "GHCN FIPS codes of countries bordering the Mediterranean; TMAX first year <= 1961 and last year >= 2024",
            "countries": sorted(MED_FIPS), "stations": total, "by_country": dict(sorted(by_country.items()))}


if __name__ == "__main__":
    main()
