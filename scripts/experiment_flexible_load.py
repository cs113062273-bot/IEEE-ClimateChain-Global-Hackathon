"""Stage-1 direction experiment: carbon value of delaying flexible batch electricity.

  .venv/Scripts/python.exe scripts/experiment_flexible_load.py

Protocol: experiments/flexible_load/protocol.json (written before results).
No battery, no car park, no product code touched. Location-based average-intensity exposure.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.lineage import ANCHORS_PATH, _trusted_bytes

OUT = ROOT / "experiments/flexible_load"
PROTOCOL = json.loads((OUT / "protocol.json").read_text())
W = PROTOCOL["workload"]
CAP_KW = W["shared_capacity_kw"]
FLEX_H = W["flexibility_hours"]
MAX_FLEX = max(FLEX_H) * 2
START = pd.Timestamp("2025-01-01", tz="UTC")
SPLITS = {"training": ("2025-01-08", "2025-05-01"), "validation": ("2025-05-01", "2025-07-01"),
          "exploratory_test": ("2025-07-01", "2026-01-01"), "independent_test": ("2026-01-01", "2026-10-17")}


# ---------------------------------------------------------------- data
def load_series():
    anchors = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))["sources"]
    raw26 = (ROOT / "data/raw/neso_ci_2026.json").read_bytes()
    frames = []
    for body in (_trusted_bytes(anchors["neso-national-ci-2025"]), raw26):
        d = pd.DataFrame(json.loads(body)["result"]["records"])
        d.index = pd.to_datetime(d.datetime, utc=True)
        frames.append(d[["actual", "forecast"]].astype(float))
    d = pd.concat(frames)
    d = d[~d.index.duplicated(keep="first")].sort_index()
    index = pd.date_range(START, d.index.max(), freq="30min")
    d = d.reindex(index)
    observed = d.actual.to_numpy()                       # NaN where the source has no value
    scored = d.actual.interpolate(limit_direction="both").to_numpy()  # only for scoring a run that crosses a gap
    published = d.forecast.to_numpy()
    meta = {"slots": len(index), "end": str(index[-1]), "missing_actual_slots": int(np.isnan(observed).sum()),
            "neso_2026_sha256": hashlib.sha256(raw26).hexdigest(), "neso_2025_sha256": anchors["neso-national-ci-2025"]["sha256"]}
    return index, observed, scored, published, meta


def slot_of(ts):
    return int((pd.Timestamp(ts, tz="UTC") - START) / pd.Timedelta(minutes=30))


# ---------------------------------------------------------------- workload
def make_jobs(n_slots):
    rng = np.random.default_rng(W["seed"])
    jobs = []
    days = n_slots // 48
    for day in range(days):
        for k in range(W["jobs_per_day"]):
            arrival = day * 48 + 16 + int(rng.integers(0, 24))          # 08:00 .. 19:30 UTC
            duration = int(rng.integers(2, 9))
            power = float(rng.choice([5, 10, 15, 20]))
            if arrival + duration + MAX_FLEX < n_slots:
                jobs.append((len(jobs), arrival, duration, power))
    return pd.DataFrame(jobs, columns=["job", "arrival", "duration", "power"]).sort_values(["arrival", "job"]).reset_index(drop=True)


# ---------------------------------------------------------------- forecasts (issue slot i sees observed[:i] only)
def ffill_last(observed):
    last = pd.Series(observed).ffill().to_numpy()
    return np.concatenate([[np.nan], last[:-1]])         # value known strictly before slot i


def seasonal(observed, i, targets):
    lags = targets[:, None] - 48 * np.arange(1, 8)[None, :]
    vals = np.where((lags < i) & (lags >= 0), observed[np.clip(lags, 0, None)], np.nan)
    with np.errstate(all="ignore"):
        out = np.nanmedian(vals, axis=1)
    return out


class Forecasts:
    def __init__(self, observed, published):
        self.observed, self.published = observed, published
        self.last = ffill_last(observed)
        a, b = slot_of(SPLITS["training"][0]), slot_of(SPLITS["training"][1])
        tod = np.arange(len(observed)) % 48
        self.profile = np.array([np.nanmean(observed[a:b][tod[a:b] == s]) for s in range(48)])
        self.tau = None; self.model = None

    def fixed(self, i, t):
        return self.profile[t % 48]

    def seasonal(self, i, t):
        s = seasonal(self.observed, i, t)
        return np.where(np.isnan(s), self.profile[t % 48], s)

    def persistence(self, i, t):
        base = self.seasonal(i, t)
        anchor = self.seasonal(i, np.array([i - 1]))[0]
        anomaly = (self.last[i] - anchor) if np.isfinite(self.last[i]) else 0.0
        return base + anomaly * np.exp(-(t - i + 1) / self.tau)

    def features(self, i, t):
        o = self.observed
        h = t - i
        recent = lambda n: np.nanmean(o[max(0, i - n):i]) if i > 0 else np.nan
        s7 = self.seasonal(i, t)
        lag = lambda k: np.where(t - 48 * k < i, o[np.clip(t - 48 * k, 0, None)], np.nan)
        anchor = self.seasonal(i, np.array([i - 1]))[0]
        n = len(t)
        return np.column_stack([h, t % 48, ((t // 48) + 2) % 7, np.full(n, i % 48), np.full(n, self.last[i]), np.full(n, recent(6)),
                                np.full(n, recent(48)), np.full(n, recent(336)), s7, lag(1), lag(2), np.full(n, self.last[i] - anchor)])

    def lightgbm(self, i, t):
        return self.model.predict(self.features(i, t), num_threads=1)

    def oracle_factory(self, scored):
        return lambda i, t: scored[t]

    def published_ref(self, i, t):
        p = self.published[t]
        return np.where(np.isnan(p), self.seasonal(i, t), p)


def fit_lightgbm(fc, config):
    from lightgbm import LGBMRegressor
    a, b = slot_of(SPLITS["training"][0]), slot_of(SPLITS["training"][1])
    X, y = [], []
    for i in range(a, b - MAX_FLEX - 8, 3):
        t = i + np.arange(0, MAX_FLEX + 8, 2)
        target = fc.observed[t]
        keep = np.isfinite(target)
        X.append(fc.features(i, t)[keep]); y.append(target[keep])
    model = LGBMRegressor(objective="l1", random_state=42, n_jobs=1, deterministic=True, force_col_wise=True, verbosity=-1, **config)
    model.fit(np.vstack(X), np.concatenate(y))
    return model


# ---------------------------------------------------------------- scheduler
def schedule(jobs, forecasts, flex_slots, n_slots, scored, tariff):
    """Online commit at arrival. Returns per-job start (or -1 missed) and usage."""
    usage = np.zeros(n_slots)
    starts = np.full(len(jobs), -1); seconds = 0.0
    for r in jobs.itertuples():
        a, d, p = r.arrival, r.duration, r.power
        last_start = a + flex_slots
        candidates = np.arange(a, last_start + 1)
        run = usage[a:last_start + d]
        windows = np.lib.stride_tricks.sliding_window_view(run, d)[: len(candidates)]
        feasible = windows.max(axis=1) + p <= CAP_KW + 1e-9
        if not feasible.any():
            continue
        if forecasts is None:
            s = candidates[np.argmax(feasible)]
        else:
            t0 = time.perf_counter()
            f = forecasts[r.Index]                       # forecast over [a, a + flex + d)
            sums = np.convolve(f[: flex_slots + d], np.ones(d), "valid")[: len(candidates)]
            sums = np.where(feasible, sums, np.inf)
            s = candidates[int(np.argmin(sums))]         # argmin returns the earliest on ties
            seconds += time.perf_counter() - t0
        starts[r.Index] = s
        usage[s:s + d] += p
    return starts, usage, seconds


def score(jobs, starts, usage, scored, tariff, index):
    rows = []
    for r, s in zip(jobs.itertuples(), starts):
        if s < 0:
            rows.append((r.arrival // 48, 0.0, 0.0, 0.0, 1, np.nan)); continue
        energy = r.power * .5 * r.duration
        co2 = r.power * .5 * scored[s:s + r.duration].sum() / 1000
        cost = r.power * .5 * tariff[np.arange(s, s + r.duration) % 48].sum()
        rows.append((r.arrival // 48, energy, co2, cost, 0, (s - r.arrival) / 2))
    out = pd.DataFrame(rows, columns=["day", "energy_kwh", "kgco2", "gbp", "missed", "delay_h"])
    daily_peak = pd.Series(usage).groupby(np.arange(len(usage)) // 48).max()
    return out, daily_peak


def block_ci(num, den, block=7, draws=2000, seed=42):
    num, den = np.asarray(num), np.asarray(den); n = len(num); rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(draws, (n + block - 1) // block))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
    vals = 100 * num[idx].sum(1) / den[idx].sum(1)
    return [float(np.quantile(vals, .025)), float(np.quantile(vals, .975))]


def main():
    started = time.perf_counter()
    index, observed, scored, published, meta = load_series()
    n = len(index)
    tariff = np.array([.12 if (s + .5) * .5 < 7 else .36 if 16 <= (s + .5) * .5 < 20 else .23 for s in range(48)])
    jobs_all = make_jobs(n)
    fc = Forecasts(observed, published)

    def period_jobs(name):
        a, b = slot_of(SPLITS[name][0]), slot_of(SPLITS[name][1])
        return jobs_all[(jobs_all.arrival >= a) & (jobs_all.arrival < b)].reset_index(drop=True)

    def forecast_vectors(jobs, fn):
        out = {}
        for r in jobs.itertuples():
            t = np.arange(r.arrival, r.arrival + MAX_FLEX + r.duration)
            out[r.Index] = fn(r.arrival, t)
        return out

    def run(jobs, vectors, flex_h):
        starts, usage, secs = schedule(jobs, vectors, int(flex_h * 2), n, scored, tariff)
        return score(jobs, starts, usage, scored, tariff, index) + (secs,)

    # ---- selection on validation (carbon at 24 h flexibility)
    val = period_jobs("validation")
    base_val, _, _ = run(val, None, 24)
    selection = {"tau_hours": {}, "lightgbm": {}}
    for tau_h in (6, 12, 24, 48, 96):
        fc.tau = tau_h * 2
        res, _, _ = run(val, forecast_vectors(val, fc.persistence), 24)
        selection["tau_hours"][tau_h] = float(100 * (1 - res.kgco2.sum() / base_val.kgco2.sum()))
    best_tau = max(selection["tau_hours"], key=selection["tau_hours"].get)
    fc.tau = best_tau * 2
    configs = {"small": dict(n_estimators=250, num_leaves=15, learning_rate=.05, min_child_samples=100),
               "large": dict(n_estimators=500, num_leaves=31, learning_rate=.03, min_child_samples=50)}
    models = {}
    for name, cfg in configs.items():
        fc.model = models[name] = fit_lightgbm(fc, cfg)
        res, _, _ = run(val, forecast_vectors(val, fc.lightgbm), 24)
        selection["lightgbm"][name] = float(100 * (1 - res.kgco2.sum() / base_val.kgco2.sum()))
    best_cfg = max(selection["lightgbm"], key=selection["lightgbm"].get)
    fc.model = models[best_cfg]
    selection.update(chosen_tau_hours=best_tau, chosen_lightgbm=best_cfg, selected_on="validation 2025-05/06, carbon at 24 h")
    print("selection", json.dumps(selection), flush=True)

    methods = {"fixed_time_of_day": fc.fixed, "seasonal_median": fc.seasonal, "persistence_blend": fc.persistence,
               "lightgbm_multi_horizon": fc.lightgbm, "perfect_foresight": fc.oracle_factory(scored), "neso_published_reference": fc.published_ref}

    # ---- forecast accuracy by horizon (validation and both tests)
    accuracy = []
    for period in ("validation", "exploratory_test", "independent_test"):
        jobs = period_jobs(period).iloc[::6]
        for name, fn in methods.items():
            if name == "perfect_foresight":
                continue
            err = {k: [] for k in ("0-6h", "6-24h", "24-52h")}
            for r in jobs.itertuples():
                t = np.arange(r.arrival, r.arrival + MAX_FLEX + 8)
                e = np.abs(fn(r.arrival, t) - observed[t]); h = (t - r.arrival) / 2
                for k, (lo, hi) in {"0-6h": (0, 6), "6-24h": (6, 24), "24-52h": (24, 53)}.items():
                    m = (h >= lo) & (h < hi) & np.isfinite(e); err[k].extend(e[m])
            accuracy.append({"period": period, "method": name, **{f"mae_{k}": float(np.mean(v)) for k, v in err.items()}})

    # ---- evaluation
    rows, daily = [], []
    for period in ("validation", "exploratory_test", "independent_test"):
        jobs = period_jobs(period)
        vectors = {name: forecast_vectors(jobs, fn) for name, fn in methods.items()}
        for flex in FLEX_H:
            imm, imm_peak, _ = run(jobs, None, flex)
            imm_day = imm.groupby("day")[["kgco2", "gbp"]].sum()
            results = {"immediate": (imm, imm_peak, 0.0)}
            if flex > 0:
                for name in methods:
                    results[name] = run(jobs, vectors[name], flex)
            oracle_red = imm.kgco2.sum() - results["perfect_foresight"][0].kgco2.sum() if flex > 0 else 0.0
            for name, (res, peak, secs) in results.items():
                day = res.groupby("day")[["kgco2", "gbp"]].sum().reindex(imm_day.index, fill_value=0)
                red = imm.kgco2.sum() - res.kgco2.sum()
                rows.append({"period": period, "flex_h": flex, "policy": name, "jobs": len(res), "missed": int(res.missed.sum()),
                             "energy_kwh": float(res.energy_kwh.sum()), "kgco2": float(res.kgco2.sum()), "gbp": float(res.gbp.sum()),
                             "reduction_pct": float(100 * red / imm.kgco2.sum()),
                             "reduction_ci95": block_ci((imm_day.kgco2 - day.kgco2).to_numpy(), imm_day.kgco2.to_numpy()) if name != "immediate" else [0.0, 0.0],
                             "cost_change_pct": float(100 * (res.gbp.sum() - imm.gbp.sum()) / imm.gbp.sum()),
                             "share_of_perfect_foresight": float(red / oracle_red) if oracle_red > 0 else None,
                             "worse_days": int(((day.kgco2 - imm_day.kgco2) > 1e-9).sum()), "days": int(len(imm_day)),
                             "mean_delay_h": float(res.delay_h.mean()), "peak_kw_max": float(peak.max()), "peak_kw_mean_daily": float(peak.mean()),
                             "decision_ms_per_job": float(1000 * secs / max(1, len(res)))})
                if flex == 24 and name in ("immediate", "persistence_blend", "lightgbm_multi_horizon", "perfect_foresight", "fixed_time_of_day", "seasonal_median"):
                    daily.append(res.assign(policy=name, period=period, job=jobs.job.to_numpy(), duration=jobs.duration.to_numpy(),
                                            arrival_hour=(jobs.arrival % 48 // 2).to_numpy()))
        print(f"{period} done {time.perf_counter() - started:.0f}s", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "results.csv", index=False)
    pd.DataFrame(accuracy).to_csv(OUT / "forecast_accuracy.csv", index=False)

    # ---- which jobs carry the value (24 h flexibility)
    jd = pd.concat(daily)
    base = jd[jd.policy == "immediate"].set_index(["period", "job"]).kgco2
    breakdown = []
    for (period, policy), g in jd[jd.policy != "immediate"].groupby(["period", "policy"]):
        g = g.set_index(["period", "job"])
        g = g.assign(base=base.loc[g.index].to_numpy())
        g["length"] = np.where(g.duration <= 4, "1-2 h jobs", "2.5-4 h jobs")
        g["arrives"] = pd.cut(g.arrival_hour, [7, 11, 15, 20], labels=["08-12", "12-16", "16-20"])
        for col in ("length", "arrives"):
            for k, h in g.groupby(col, observed=True):
                breakdown.append({"period": period, "policy": policy, "group": col, "value": str(k), "jobs": len(h),
                                  "reduction_pct": float(100 * (h.base.sum() - h.kgco2.sum()) / h.base.sum())})
    pd.DataFrame(breakdown).to_csv(OUT / "breakdown_24h.csv", index=False)
    summary = {"protocol_sha256": hashlib.sha256((OUT / "protocol.json").read_bytes()).hexdigest(), "data": meta,
               "jobs": {p: int(len(period_jobs(p))) for p in SPLITS if p != "training"}, "selection": selection,
               "flexible_energy_kwh_per_day": float(jobs_all.eval("power*0.5*duration").sum() / (n // 48)),
               "wall_seconds": time.perf_counter() - started}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8", newline="\n")
    pd.set_option("display.width", 250)
    show = frame[frame.period != "validation"].pivot_table(index=["period", "policy"], columns="flex_h", values="reduction_pct").round(1)
    print(show.to_string())
    print(json.dumps(summary, indent=1, default=float))


if __name__ == "__main__":
    main()
