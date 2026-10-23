"""Exploratory follow-up after external review (see experiments/carpark_followup/protocol.json).

  .venv/Scripts/python.exe scripts/evaluate_carpark_followup.py

Q1: decision-time inputs (fixed 11 kW, declared uncapped requests, nothing dropped).
Q2: simple personal-history departure estimators versus LightGBM under the same scheduler.
2024 was already examined once, so nothing here is independent validation.
Published experiments/carpark outputs are not modified.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.fleet.controller import Car, Site, simulate, deliverable_kwh, SERVED_TOL_KWH
from backend.app.fleet.day import make_cars
from backend.app.fleet.inputs import decision_cars, infeasible
from backend.app.fleet.departure import driver_histories
from backend.app.fleet.grid import grid_day
from backend.app.fleet.model import frozen, quantile_table, FIT
from backend.app.fleet.sessions import day_sessions, grid_date, site_days
from scripts.evaluate_carpark import block_ci
from scripts.sensitivity_carpark import typical_requests, unknown_requests

OUT = ROOT / "experiments/carpark_followup"
LEVELS = (0.05, 0.1, 0.2, 0.35, 0.5)
KS = (2, 4, 8, 16, 32)
SEL_CAPS = range(100, 161, 10)
TEST_CAPS = range(80, 201, 10)
LP_CAPS = (100, 120, 150)
GRID = np.arange(0, 17.0001, 0.05)
MIN_HISTORY = 3


def personal_quantiles(df, ks, levels, rows):
    """Grid-based mixture quantiles: driver's past dwell CDF mixed with k population pseudo-sessions."""
    fit = df[(df.date >= FIT[0]) & (df.date < FIT[1])]
    bins = np.clip(fit.arrival_h.astype(int), 4, 16)
    pop = {b: np.sort(g.to_numpy()) for b, g in fit.dwell_h.groupby(bins)}
    pop_all = np.sort(fit.dwell_h.to_numpy())
    pop_cdf = {b: np.searchsorted(v, GRID, side="right") / len(v) for b, v in pop.items()}
    all_cdf = np.searchsorted(pop_all, GRID, side="right") / len(pop_all)
    history = driver_histories(df)
    out = {k: {} for k in ks}
    for idx in rows:
        b = int(np.clip(int(df.at[idx, "arrival_h"]), 4, 16))
        F_pop = pop_cdf.get(b, all_cdf)
        past = history.get(idx)
        n = 0 if past is None else len(past)
        F_personal = np.searchsorted(np.sort(past), GRID, side="right") / n if n else None
        for k in ks:
            if n < MIN_HISTORY:
                F = F_pop
            elif k == 0:
                F = F_personal
            else:
                F = (n * F_personal + k * F_pop) / (n + k)
            out[k][df.at[idx, "session_id"]] = [float(GRID[min(len(GRID) - 1, np.searchsorted(F, a, side="left"))]) for a in levels]
    return out


def infeasible_count(cars):
    return sum(infeasible(c) for c in cars)


def run(cars, grid, cap, policy, **tags):
    r = simulate(cars, grid, Site(connection_kw=cap), policy)
    return {**tags, "cap": cap, **{k: r[k] for k in ("sessions", "served", "requested_kwh", "unserved_kwh", "emissions_kgco2", "cap_exceeded_slots")}}


def promise_fn(name, level, personal):
    """name: population | lightgbm | personal_k (k=0 is the pure personal quantile)."""
    def fn(sessions):
        a = sessions.arrival_h.to_numpy()
        if name in ("population", "lightgbm"):
            return a + quantile_table(name).loc[sessions.session_id, level].to_numpy()
        k = int(name.split("_")[1])
        j = LEVELS.index(level)
        return a + np.array([personal[k][sid][j] for sid in sessions.session_id])
    return fn


def families():
    yield "population", None
    yield "lightgbm", None
    yield "personal_0", None
    for k in KS:
        yield f"personal_{k}", None


def summarise(frame, keys):
    g = frame.groupby(keys, dropna=False)
    out = g[["sessions", "served", "requested_kwh", "unserved_kwh", "cap_exceeded_slots", "infeasible"]].sum()
    out["served_pct"] = 100 * out.served / out.sessions
    out["served_of_feasible_pct"] = 100 * out.served / (out.sessions - out.infeasible)
    out["unserved_pct"] = 100 * out.unserved_kwh / out.requested_kwh
    out["emissions_kgco2_per_day"] = g.emissions_kgco2.mean()
    return out.reset_index()


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    original_selection = json.loads((ROOT / "experiments/carpark/selection.json").read_text())
    _, _, df, _ = frozen()
    val_days = [d for d in site_days("validation") if d >= "2023-07-01"]
    test_days = site_days("test")
    rows = df.index[df.site & df.date.isin(set(val_days) | set(test_days))]
    personal = personal_quantiles(df, (0,) + KS, LEVELS, rows)
    typical = typical_requests(df)
    print(f"personal quantiles for {len(rows)} sessions in {time.perf_counter() - started:.0f} s", flush=True)

    # Selection on 2023 H2 under the decision-time regime, each family separately.
    sel_rows = []
    for d in val_days:
        sessions, grid = day_sessions(d), grid_day(grid_date(d))
        for name, _ in families():
            for level in LEVELS:
                cars = decision_cars(sessions, promise_fn(name, level, personal)(sessions))
                n_inf = infeasible_count(cars)
                for cap in SEL_CAPS:
                    sel_rows.append({**run(cars, grid, cap, "edf", day=d, model=name, level=level), "infeasible": n_inf})
        cars = decision_cars(sessions, sessions.departure_h.to_numpy())
        for cap in SEL_CAPS:
            sel_rows.append({**run(cars, grid, cap, "equal_share", day=d, model="none", level=None), "infeasible": infeasible_count(cars)})
    sel = pd.DataFrame(sel_rows)
    sel_summary = summarise(sel, ["model", "level", "cap"])
    sel_summary.to_csv(OUT / "selection_summary.csv", index=False)
    ranked = sel_summary[sel_summary.model != "none"].groupby(["model", "level"]).agg(mean_served=("served_pct", "mean"), mean_unserved=("unserved_pct", "mean")).reset_index()
    ranked["family"] = ranked.model.str.replace(r"_(2|4|8|16|32)$", "_k", regex=True)
    chosen = {}
    for family, g in ranked.groupby("family"):
        best = g.sort_values(["mean_served", "mean_unserved"], ascending=[False, True]).iloc[0]
        chosen[family] = {"model": best.model, "level": float(best.level), "selection_mean_served_pct": float(best.mean_served),
                          "selection_mean_unserved_pct": float(best.mean_unserved)}
    selection = {"selected_utc": pd.Timestamp.now(tz="UTC").isoformat(), "regime": "decision_time", "days": len(val_days),
                 "chosen": chosen, "ranking": ranked.sort_values("mean_served", ascending=False).to_dict("records"),
                 "original_lightgbm_choice": original_selection["service_policy"],
                 "protocol_sha256": hashlib.sha256((OUT / "protocol.json").read_bytes()).hexdigest()}
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2, default=float), encoding="utf-8", newline="\n")
    print(json.dumps(chosen, indent=1), flush=True)

    variants = {"edf_population": ("population", chosen["population"]["level"]),
                "edf_personal_quantile": ("personal_0", chosen["personal_0"]["level"]),
                "edf_shrinkage": (chosen["personal_k"]["model"], chosen["personal_k"]["level"]),
                "edf_lightgbm": ("lightgbm", chosen["lightgbm"]["level"]),
                "edf_lightgbm_original_choice": ("lightgbm", float(original_selection["service_policy"]["level"]))}
    flex = original_selection["carbon_flex"]
    test_rows = []
    for n, d in enumerate(test_days):
        sessions, grid = day_sessions(d), grid_day(grid_date(d))
        builds = {}
        for vname, (model, level) in variants.items():
            p = promise_fn(model, level, personal)(sessions)
            builds[vname] = {"decision_time": decision_cars(sessions, p), "original": make_cars(sessions, p)[0]}
        truth = {"decision_time": decision_cars(sessions, sessions.departure_h.to_numpy()), "original": make_cars(sessions, sessions.departure_h.to_numpy())[0]}
        inf = {r: infeasible_count(c) for r, c in truth.items()}
        for regime in ("decision_time", "original"):
            for cap in TEST_CAPS:
                tag = dict(day=d, regime=regime, infeasible=inf[regime])
                test_rows.append(run(truth[regime], grid, cap, "equal_share", policy_name="equal_share", **tag))
                test_rows.append(run(truth[regime], grid, cap, "edf", policy_name="edf_oracle_departures", **tag))
                for vname, b in builds.items():
                    test_rows.append(run(b[regime], grid, cap, "edf", policy_name=vname, **tag))
        for cap in LP_CAPS:
            site = Site(connection_kw=cap)
            tag = dict(day=d, regime="decision_time_past_requests", infeasible=inf["decision_time"], cap=cap)
            for vname, policy in [("equal_share", "equal_share")] + [(v, "edf") for v in variants]:
                cars = truth["decision_time"] if vname == "equal_share" else builds[vname]["decision_time"]
                r = unknown_requests(cars, grid, site, policy, typical)
                test_rows.append({**tag, "policy_name": vname, **{k: r[k] for k in ("sessions", "served", "requested_kwh", "unserved_kwh", "emissions_kgco2", "cap_exceeded_slots")}})
            # Carbon-flex LP under decision-time inputs (LightGBM risk distribution, as selected originally).
            q = quantile_table("lightgbm").loc[sessions.session_id].to_numpy()
            model = frozen()[0]["lightgbm"]
            lp_cars = decision_cars(sessions, np.full(len(sessions), 24.0))
            for c, a, qq in zip(lp_cars, sessions.arrival_h.to_numpy(), q):
                c.risk = model.risk_points(a, qq)
            r = simulate(lp_cars, grid, replace(site, risk_penalty=flex["risk_penalty"]), "optimised")
            test_rows.append({"day": d, "regime": "decision_time", "infeasible": inf["decision_time"], "cap": cap, "policy_name": "carbon_flex",
                              **{k: r[k] for k in ("sessions", "served", "requested_kwh", "unserved_kwh", "emissions_kgco2", "cap_exceeded_slots")}})
        if (n + 1) % 20 == 0:
            print(f"test {n + 1}/{len(test_days)}", flush=True)
    test = pd.DataFrame(test_rows)
    test.to_csv(OUT / "test_daily.csv", index=False)
    summary = summarise(test, ["regime", "policy_name", "cap"])
    summary.to_csv(OUT / "test_summary.csv", index=False)

    paired = []
    pairs = [("edf_lightgbm", "equal_share"), ("edf_shrinkage", "equal_share"), ("edf_personal_quantile", "equal_share"),
             ("edf_lightgbm", "edf_shrinkage"), ("edf_lightgbm", "edf_personal_quantile"), ("edf_shrinkage", "edf_population"),
             ("edf_lightgbm", "edf_population"), ("carbon_flex", "equal_share"),
             ("edf_lightgbm_original_choice", "equal_share"), ("edf_lightgbm_original_choice", "edf_personal_quantile"),
             ("edf_personal_quantile", "edf_population"), ("edf_lightgbm_original_choice", "edf_population")]
    for regime in ("decision_time", "original", "decision_time_past_requests"):
        for cap in LP_CAPS:
            at = test[(test.regime == regime) & (test.cap == cap)].set_index(["day", "policy_name"])
            names = set(at.index.get_level_values(1))
            for a, b in pairs:
                if a not in names or b not in names:
                    continue
                for metric in ("served", "unserved_kwh", "emissions_kgco2"):
                    diff = (at.xs(a, level=1)[metric] - at.xs(b, level=1)[metric]).loc[test_days]
                    better = (diff > 1e-9) if metric == "served" else (diff < -1e-9)
                    worse = (diff < -1e-9) if metric == "served" else (diff > 1e-9)
                    paired.append({"regime": regime, "cap": cap, "a": a, "b": b, "metric": metric, "mean_diff_per_day": float(diff.mean()),
                                   "block_ci95": block_ci(diff.to_numpy()), "days_a_better": int(better.sum()), "days_a_worse": int(worse.sum())})
    capacity = {}
    for (regime, name), g in summary[summary.regime != "decision_time_past_requests"].groupby(["regime", "policy_name"]):
        if g.cap.nunique() < 5:
            continue
        capacity.setdefault(regime, {})[name] = {f">={t}%": (int(g[g.served_pct >= t].cap.min()) if (g.served_pct >= t).any() else None) for t in (90, 95, 98)}
    result = {"days": len(test_days), "selection": chosen, "capacity_needed_kw": capacity, "paired": paired,
              "infeasible_requests_decision_time": int(test[(test.regime == "decision_time") & (test.cap == 100) & (test.policy_name == "equal_share")].infeasible.sum()),
              "sessions": int(test[(test.regime == "decision_time") & (test.cap == 100) & (test.policy_name == "equal_share")].sessions.sum()),
              "wall_seconds": time.perf_counter() - started}
    (OUT / "test_results.json").write_text(json.dumps(result, indent=2, default=float), encoding="utf-8", newline="\n")
    print(json.dumps(capacity, indent=1))
    print(f"{result['wall_seconds']:.0f} s")


if __name__ == "__main__":
    main()
