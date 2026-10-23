"""Evaluate gap-filling methods under the frozen protocol (ml/protocol.json).

Run from the repository root with the dev environment:
    extremeproof/.venv/Scripts/python -m extremeproof.ml.evaluate

Writes ml/report.json (all numbers) and ml/lightgbm_antalya.txt (the model the
station provider would use if the AI is adopted). Never reads the station's own
value on a day it is estimating; test-period station values are used only to
score.
"""
import hashlib
import json
import math
from datetime import date
from pathlib import Path

import lightgbm as lgb
import numpy as np

from extremeproof.climate import engine as E
from extremeproof.climate import fill as F
from extremeproof.climate.sources import load_ghcn, load_open_meteo

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "ml"
RAW = ROOT / "data" / "raw"
PROTOCOL_PATH = ML / "protocol.json"
FIT_END = date(2010, 12, 31)
TEST_START, TEST_END = date(2011, 1, 1), date(2025, 12, 31)
START = date(1963, 1, 1)
BASE = (date(1961, 1, 1), date(1990, 12, 31))
SEASON = ((6, 1), (9, 30))
MIN_SPELL = 6
BASELINES = ("era5_raw", "era5_monthly_linear", "era5_quantile_map")
AI = "lightgbm_gap_fill"
MIN_FIT_DAYS = 365 * 3
# Post-hoc exploratory analysis (added after the pre-registered results; never used for the decision):
# the 1991-2020 base, scored on 2021-2026 summers, which lie outside that base.
EXPLORE_BASE = (date(1991, 1, 1), date(2020, 12, 31))
EXPLORE_YEARS = (2021, 2026)
FEATURES = ["e_tx", "e_tx_m1", "e_tx_p1", "e_tn", "el_tx", "doy_sin", "doy_cos"]


def load_station(sid):
    st, _ = load_ghcn(RAW / "ghcn" / f"{sid}.csv", "TMAX")
    e_tx, meta = load_open_meteo(RAW / "era5" / f"{sid}_era5.json", "temperature_2m_max")
    e_tn, _ = load_open_meteo(RAW / "era5" / f"{sid}_era5.json", "temperature_2m_min")
    el_tx, _ = load_open_meteo(RAW / "era5" / f"{sid}_era5_land.json", "temperature_2m_max")
    stations = json.loads((ROOT / "data" / "stations.json").read_text(encoding="utf-8"))["stations"]
    elev_diff = stations[sid]["elev_m"] - float(meta["elevation"])
    return {"st": st, "e_tx": e_tx, "e_tn": e_tn, "el_tx": el_tx, "elev_diff": elev_diff}


def feature_row(S, d, spatial):
    one = date.fromordinal
    o = d.toordinal()
    row = [S["e_tx"].get(d), S["e_tx"].get(one(o - 1)), S["e_tx"].get(one(o + 1)), S["e_tn"].get(d), S["el_tx"].get(d)]
    ang = 2 * math.pi * (E.doy(d) - 1) / 365.25
    row += [math.sin(ang), math.cos(ang)]
    if spatial:
        row.append(S["elev_diff"])
    return [np.nan if v is None else v for v in row]


def matrix(S, days, spatial):
    return np.array([feature_row(S, d, spatial) for d in days], dtype="float64")


def fit_lgb(X, y, params):
    p = dict(params)
    n = p.pop("n_estimators")
    seed = p.pop("seed")
    p.update(seed=seed, verbose=-1, num_threads=1)
    return lgb.train(p, lgb.Dataset(X, label=y), num_boost_round=n)


class Methods:
    """Fitted gap-filling methods for one target station (per-station or pooled)."""

    def __init__(self, pairs, X, y, lgb_params):
        self.params = {m: F.fit_pairs(m, pairs) for m in BASELINES}
        self.model = fit_lgb(X, y, lgb_params)

    def predict(self, method, S, days, spatial):
        if method == AI:
            return list(self.model.predict(matrix(S, days, spatial)))
        return [F.predict(self.params[method], d, S["e_tx"].get(d)) for d in days]


def training_rows(S, spatial):
    days = [d for d in S["st"] if START <= d <= FIT_END and d in S["e_tx"]]
    days.sort()
    pairs = [(d, S["st"][d], S["e_tx"][d]) for d in days]
    return pairs, matrix(S, days, spatial), np.array([S["st"][d] for d in days])


def layer1(S, methods, spatial):
    days = sorted(d for d in S["st"] if TEST_START <= d <= TEST_END and d in S["e_tx"])
    obs = np.array([S["st"][d] for d in days])
    summer = np.array([d.month in (6, 7, 8, 9) for d in days])
    hot_cut = float(np.quantile(obs[summer], 0.9)) if summer.any() else float("inf")
    hot = summer & (obs >= hot_cut)
    out = {"test_days": len(days), "hot_days": int(hot.sum()), "hot_cutoff_degC": round(hot_cut, 2)}
    for m in BASELINES + (AI,):
        pred = np.array(methods.predict(m, S, days, spatial), dtype="float64")
        err = pred - obs
        out[m] = {"mae": round(float(np.nanmean(np.abs(err))), 3),
                  "mae_hot": round(float(np.nanmean(np.abs(err[hot]))), 3) if hot.any() else None,
                  "bias_hot": round(float(np.nanmean(err[hot])), 3) if hot.any() else None}
    return out


def gap_patterns(antalya):
    pats = {}
    for y in (2023, 2024):
        pats[f"antalya_{y}"] = {(d.month, d.day) for d in E.season_dates(y, SEASON) if d not in antalya["st"]}
    pats["whole_season"] = {(d.month, d.day) for d in E.season_dates(2001, SEASON)}
    return pats


def layer2(S, methods, spatial, patterns, base=BASE, years=(TEST_START.year, TEST_END.year)):
    present, total = E.completeness(S["st"], *base)
    if present * 1000 // total < 600:
        return {"excluded": f"base coverage {present}/{total} below 60 %"}
    th = E.percentile_doy(S["st"], *base)
    seasons = [y for y in range(years[0], years[1] + 1)
               if all(d in S["st"] for d in E.season_dates(y, SEASON))]
    rows = []
    for y in seasons:
        days = E.season_dates(y, SEASON)
        truth_ls = E.longest_spell(S["st"], th, y, SEASON)
        preds = {m: dict(zip(days, methods.predict(m, S, days, spatial))) for m in BASELINES + (AI,)}
        for pname, mask in patterns.items():
            gap = [d for d in days if (d.month, d.day) in mask]
            if not gap:
                continue
            row = {"year": y, "pattern": pname, "gap_days": len(gap), "truth_longest": truth_ls,
                   "truth": truth_ls >= MIN_SPELL}
            for m in BASELINES + (AI,):
                filled = dict(S["st"])
                for d in gap:
                    filled[d] = preds[m][d]
                ls = E.longest_spell(filled, th, y, SEASON)
                row[m] = ls
            rows.append(row)
    return {"base_coverage_permille": present * 1000 // total, "eligible_seasons": seasons, "rows": rows}


def summarise(per_station, key="layer2"):
    out = {}
    for m in BASELINES + (AI,):
        agree = false_trig = missed = n = 0
        spell_err = []
        by_pattern = {}
        for res in per_station.values():
            for r in res[key].get("rows", []):
                v = r[m] >= MIN_SPELL
                n += 1
                agree += v == r["truth"]
                false_trig += v and not r["truth"]
                missed += r["truth"] and not v
                spell_err.append(abs(r[m] - r["truth_longest"]))
                bp = by_pattern.setdefault(r["pattern"], [0, 0])
                bp[0] += v == r["truth"]
                bp[1] += 1
        out[m] = {"seasons_scored": n, "agree": agree, "false_triggers": false_trig, "missed_triggers": missed,
                  "true_trigger_seasons": sum(r["truth"] for res in per_station.values() for r in res[key].get("rows", [])),
                  "longest_spell_mae": round(sum(spell_err) / len(spell_err), 3) if spell_err else None,
                  "agree_by_pattern": {k: f"{a}/{b}" for k, (a, b) in sorted(by_pattern.items())}}
        mae = [res["layer1"][m]["mae"] for res in per_station.values()]
        hot = [res["layer1"][m]["mae_hot"] for res in per_station.values() if res["layer1"][m]["mae_hot"] is not None]
        out[m]["layer1_mean_station_mae"] = round(sum(mae) / len(mae), 3)
        out[m]["layer1_mean_station_mae_hot"] = round(sum(hot) / len(hot), 3)
    best = sorted(BASELINES, key=lambda m: (-out[m]["agree"], out[m]["longest_spell_mae"]))[0]
    ai = out[AI]
    adopt = ai["agree"] > out[best]["agree"] and ai["longest_spell_mae"] <= out[best]["longest_spell_mae"]
    return {"methods": out, "best_baseline": best, "ai_adopted": adopt, "default_fill": AI if adopt else best}


def main():
    protocol_bytes = PROTOCOL_PATH.read_bytes()
    protocol = json.loads(protocol_bytes)
    sids = protocol["stations"]
    data = {sid: load_station(sid) for sid in sids}
    patterns = gap_patterns(data["TUM00017300"])
    report = {"protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(), "gap_pattern_sizes": {k: len(v) for k, v in patterns.items()}}

    temporal, excluded = {}, {}
    for sid in sids:
        S = data[sid]
        pairs, X, y = training_rows(S, spatial=False)
        # Deviation recorded in REPORT.md: a station with almost no observations before
        # 2011 cannot be fitted per station; it stays in the spatial design only.
        if len(pairs) < MIN_FIT_DAYS:
            excluded[sid] = f"only {len(pairs)} paired station days in 1963-2010 (need {MIN_FIT_DAYS})"
            print("temporal", sid, "excluded:", excluded[sid])
            continue
        methods = Methods(pairs, X, y, protocol["lightgbm"])
        temporal[sid] = {"fit_days": len(pairs), "layer1": layer1(S, methods, False), "layer2": layer2(S, methods, False, patterns),
                         "explore": layer2(S, methods, False, patterns, EXPLORE_BASE, EXPLORE_YEARS)}
        if sid == "TUM00017300":
            methods.model.save_model(str(ML / "lightgbm_antalya.txt"))
        print("temporal", sid, temporal[sid]["layer1"]["era5_quantile_map"], temporal[sid]["layer1"][AI])
    report["temporal"] = {"per_station": temporal, "excluded": excluded, "summary": summarise(temporal),
                          "exploratory_post_hoc": summarise(temporal, "explore")}

    spatial = {}
    for sid in sids:
        pairs, Xs, ys = [], [], []
        for other in sids:
            if other == sid:
                continue
            p, X, y = training_rows(data[other], spatial=True)
            pairs += p
            Xs.append(X)
            ys.append(y)
        methods = Methods(pairs, np.vstack(Xs), np.concatenate(ys), protocol["lightgbm"])
        S = data[sid]
        spatial[sid] = {"fit_days": len(pairs), "layer1": layer1(S, methods, True), "layer2": layer2(S, methods, True, patterns),
                        "explore": layer2(S, methods, True, patterns, EXPLORE_BASE, EXPLORE_YEARS)}
        print("spatial", sid, spatial[sid]["layer1"]["era5_quantile_map"], spatial[sid]["layer1"][AI])
    report["spatial"] = {"per_station": spatial, "summary": summarise(spatial),
                         "exploratory_post_hoc": summarise(spatial, "explore")}

    (ML / "report.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for design, part in (("temporal", "summary"), ("spatial", "summary"), ("temporal", "exploratory_post_hoc"), ("spatial", "exploratory_post_hoc")):
        s = report[design][part]
        print("==", part)
        print(design, "best baseline:", s["best_baseline"], "AI adopted:", s["ai_adopted"])
        for m, v in s["methods"].items():
            print(f"  {m:22s} agree {v['agree']}/{v['seasons_scored']} false {v['false_triggers']} missed {v['missed_triggers']} "
                  f"spellMAE {v['longest_spell_mae']} MAE {v['layer1_mean_station_mae']} hotMAE {v['layer1_mean_station_mae_hot']} {v['agree_by_pattern']}")


if __name__ == "__main__":
    main()
