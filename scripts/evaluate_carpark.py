"""Car-park departure-risk evaluation: select on 2023 H2, test once on 2024.

  .venv/Scripts/python.exe scripts/evaluate_carpark.py --stage validate
  .venv/Scripts/python.exe scripts/evaluate_carpark.py --stage test

`validate` writes selection.json (frozen choices + protocol/model/code hashes).
`test` refuses to run if the protocol or model changed after selection. Outputs
are day-level aggregates only; session-level rows stay in gitignored data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import sys
import time
from dataclasses import replace, asdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.fleet.controller import Site, simulate
from backend.app.fleet.day import make_cars
from backend.app.fleet.grid import grid_day
from backend.app.fleet.model import frozen, promises, model_fingerprint
from backend.app.fleet.sessions import SOURCE, day_sessions, grid_date, site_days

OUT = ROOT / "experiments/carpark"
PROTOCOL = OUT / "protocol.json"
CODE = ["backend/app/fleet/controller.py", "backend/app/fleet/departure.py", "backend/app/fleet/model.py",
        "backend/app/fleet/sessions.py", "backend/app/fleet/grid.py", "backend/app/fleet/day.py", "scripts/evaluate_carpark.py"]
METRICS = ["sessions", "served", "requested_kwh", "delivered_kwh", "unserved_kwh", "max_unserved_kwh", "emissions_kgco2",
           "cost_gbp", "peak_import_kw", "peak_envelope_kw", "cap_exceeded_slots", "solves", "solve_seconds"]


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def run(cars, grid, site, policy, **tags):
    started = time.perf_counter()
    result = simulate(cars, grid, site, policy)
    row = {k: result[k] for k in METRICS}
    row.update(tags, policy_name=tags.get("policy_name", policy), wall_seconds=time.perf_counter() - started)
    return row


def day_inputs(date):
    sessions = day_sessions(date)
    return sessions, grid_day(grid_date(date))


def cars_for(sessions, base=None, level=None, risk=False, hard=None):
    if base is None:  # oracle: true departure as the promise
        return make_cars(sessions, sessions.departure_h.to_numpy())[0]
    promise, risks, q = promises(sessions, base, level or .2)
    if hard is not None or risk:
        hard_promise = promises(sessions, base, hard)[0] if hard is not None else np.full(len(sessions), 24.0)
        return make_cars(sessions, hard_promise, risks=risks if risk else None)[0]
    return make_cars(sessions, promise)[0]


def summarise(frame, keys):
    g = frame.groupby(keys, dropna=False)
    out = g[["sessions", "served", "requested_kwh", "unserved_kwh", "cap_exceeded_slots"]].sum()
    out["days"] = g.size()
    out["served_pct"] = 100 * out.served / out.sessions
    out["unserved_pct"] = 100 * out.unserved_kwh / out.requested_kwh
    for k in ["emissions_kgco2", "cost_gbp", "peak_import_kw", "solve_seconds"]:
        out[k + "_per_day"] = g[k].mean()
    return out.reset_index()


def validate(args):
    days = [d for d in site_days("validation") if d >= "2023-07-01"][:args.days]
    protocol = json.loads(PROTOCOL.read_text())
    levels = protocol["candidates"]["promise_levels"]
    rows = []
    for n, date in enumerate(days):
        sessions, grid = day_inputs(date)
        oracle = cars_for(sessions)
        variants = {(b, l): cars_for(sessions, b, l) for b in ("lightgbm", "population") for l in levels}
        for cap in range(100, 161, 10):
            site = Site(connection_kw=cap)
            rows.append(run(oracle, grid, site, "equal_share", day=date, cap=cap, model="none", level=None))
            for policy in ("edf", "llf"):
                for (b, l), cars in variants.items():
                    rows.append(run(cars, grid, site, policy, day=date, cap=cap, model=b, level=l))
        site = Site(connection_kw=150)
        for lam in protocol["candidates"]["carbon_flex_lp"]["risk_penalty"]:
            for hard in protocol["candidates"]["carbon_flex_lp"]["hard_promise_level"]:
                cars = cars_for(sessions, "lightgbm", risk=True, hard=hard)
                rows.append(run(cars, grid, replace(site, risk_penalty=lam), "optimised", day=date, cap=150,
                                model="lightgbm", level=hard, risk_penalty=lam, policy_name="carbon_flex"))
        print(f"validate {n + 1}/{len(days)} {date}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "selection_daily.csv", index=False)
    summary = summarise(frame, ["policy_name", "model", "level", "risk_penalty", "cap"]) if "risk_penalty" in frame else None
    summary.to_csv(OUT / "selection_summary.csv", index=False)
    service = summary[summary.policy_name.isin(["edf", "llf"])]
    ranked = service.groupby(["policy_name", "model", "level"]).agg(mean_served=("served_pct", "mean"), mean_unserved=("unserved_pct", "mean")).reset_index()
    ranked = ranked.sort_values(["mean_served", "mean_unserved"], ascending=[False, True])
    best = ranked.iloc[0]
    equal150 = summary[(summary.policy_name == "equal_share") & (summary.cap == 150)].iloc[0]
    flex = summary[summary.policy_name == "carbon_flex"].copy()
    flex["carbon_reduction_pct"] = 100 * (equal150.emissions_kgco2_per_day - flex.emissions_kgco2_per_day) / equal150.emissions_kgco2_per_day
    qualified = flex[flex.served_pct >= equal150.served_pct]
    flagged = qualified.empty
    choice = (flex.sort_values("served_pct", ascending=False) if flagged else qualified.sort_values("carbon_reduction_pct", ascending=False)).iloc[0]
    selection = {
        "selected_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "selection_days": len(days), "selection_window": [days[0], days[-1]],
        "service_policy": {"policy": best.policy_name, "model": best.model, "level": float(best.level),
                           "selection_mean_served_pct": float(best.mean_served), "selection_mean_unserved_pct": float(best.mean_unserved)},
        "population_ablation": {"policy": best.policy_name, "model": "population", "level": float(best.level)},
        "carbon_flex": {"risk_penalty": float(choice.risk_penalty), "hard_promise_level": None if pd.isna(choice.level) else float(choice.level),
                        "selection_served_pct": float(choice.served_pct), "selection_carbon_reduction_pct": float(choice.carbon_reduction_pct),
                        "flagged_below_equal_share_service": bool(flagged)},
        "ranking_top10": ranked.head(10).to_dict("records"),
        "protocol_sha256": sha("experiments/carpark/protocol.json"), "model_fingerprint": model_fingerprint(),
        "code_sha256": {p: sha(p) for p in CODE}, "site": asdict(Site()),
    }
    (OUT / "selection.json").write_text(json.dumps(selection, indent=2, default=float))
    print(json.dumps(selection["service_policy"], indent=2), json.dumps(selection["carbon_flex"], indent=2))


def block_ci(values, block=5, draws=2000, seed=42):
    v = np.asarray(values, dtype=float); n = len(v); rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(draws, (n + block - 1) // block))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
    means = v[idx].mean(axis=1)
    return [float(np.quantile(means, .025)), float(np.quantile(means, .975))]


def test(args):
    selection = json.loads((OUT / "selection.json").read_text())
    if selection["protocol_sha256"] != sha("experiments/carpark/protocol.json"):
        raise SystemExit("Protocol changed after selection; refusing to run the test stage")
    if selection["model_fingerprint"] != model_fingerprint():
        raise SystemExit("Departure model changed after selection; refusing to run the test stage")
    protocol = json.loads(PROTOCOL.read_text())
    sp, flex = selection["service_policy"], selection["carbon_flex"]
    excluded = []
    days = site_days("test", excluded)[:args.days]
    started = time.perf_counter(); rows = []
    for n, date in enumerate(days):
        sessions, grid = day_inputs(date)
        oracle = cars_for(sessions)
        chosen = cars_for(sessions, "lightgbm", sp["level"])
        ablation = cars_for(sessions, "population", sp["level"])
        flexcars = cars_for(sessions, "lightgbm", risk=True, hard=flex["hard_promise_level"])
        for cap in protocol["caps_kw"]:
            site = Site(connection_kw=cap)
            tag = dict(day=date, cap=cap, sessions_date=date, grid_date=grid_date(date))
            rows.append(run(oracle, grid, site, "uncontrolled", **tag, policy_name="uncontrolled"))
            rows.append(run(oracle, grid, site, "equal_share", **tag, policy_name="equal_share"))
            rows.append(run(chosen, grid, site, sp["policy"], **tag, policy_name="gridproof_priority"))
            rows.append(run(ablation, grid, site, sp["policy"], **tag, policy_name="priority_population_model"))
            rows.append(run(oracle, grid, site, sp["policy"], **tag, policy_name="priority_oracle_departures"))
            if cap in protocol["lp_caps_kw"]:
                rows.append(run(flexcars, grid, replace(site, risk_penalty=flex["risk_penalty"]), "optimised", **tag, policy_name="gridproof_carbon_flex"))
                rows.append(run(oracle, grid, site, "optimised", **tag, policy_name="carbon_flex_oracle_departures"))
        print(f"test {n + 1}/{len(days)} {date}", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "test_daily.csv", index=False)
    summary = summarise(frame, ["policy_name", "cap"])
    summary.to_csv(OUT / "test_summary.csv", index=False)
    capacity = {}
    for name, g in summary.groupby("policy_name"):
        capacity[name] = {f">={t}%": (int(g[g.served_pct >= t].cap.min()) if (g.served_pct >= t).any() else None) for t in (95, 98, 99)}
    paired = []
    for cap in (100, 120, 150):
        at = frame[frame.cap == cap].set_index(["day", "policy_name"])
        for a, b in [("gridproof_priority", "equal_share"), ("gridproof_priority", "priority_population_model"),
                     ("gridproof_carbon_flex", "equal_share"), ("gridproof_carbon_flex", "gridproof_priority")]:
            if (a not in at.index.get_level_values(1)) or (b not in at.index.get_level_values(1)):
                continue
            A, B = at.xs(a, level=1), at.xs(b, level=1)
            for metric in ("served", "unserved_kwh", "emissions_kgco2", "cost_gbp", "peak_import_kw"):
                diff = (A[metric] - B[metric]).loc[days]
                paired.append({"cap": cap, "a": a, "b": b, "metric": metric, "mean_diff_per_day": float(diff.mean()),
                               "block_ci95": block_ci(diff.to_numpy()), "days_a_better": int(((diff > 1e-9) if metric == "served" else (diff < -1e-9)).sum()),
                               "days_a_worse": int(((diff < -1e-9) if metric == "served" else (diff > 1e-9)).sum())})
    models, X, df, meta = frozen()
    test_mask = ((df.date >= "2024-01-01") & (df.date < "2024-10-03")).to_numpy()
    site_mask = test_mask & df.site.to_numpy()
    coverage = {b: {"all_rails": models[b].coverage(df[test_mask], X[test_mask]), "site": models[b].coverage(df[site_mask], X[site_mask])} for b in models}
    result = {
        "evaluated_utc": pd.Timestamp.now(tz="UTC").isoformat(), "days": len(days), "excluded_days": excluded,
        "sessions": int(frame[(frame.policy_name == "equal_share") & (frame.cap == 150)].sessions.sum()),
        "selection": selection, "capacity_needed_kw": capacity, "paired": paired,
        "departure_coverage_test": coverage, "model_meta": meta, "source": SOURCE,
        "wall_seconds": time.perf_counter() - started,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "code_sha256": {p: sha(p) for p in CODE},
    }
    (OUT / "test_results.json").write_text(json.dumps(result, indent=2, default=float))
    print(json.dumps(capacity, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validate", "test"], required=True)
    parser.add_argument("--days", type=int, help="Development subset only; never for reported results")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    (validate if args.stage == "validate" else test)(args)


if __name__ == "__main__":
    main()
