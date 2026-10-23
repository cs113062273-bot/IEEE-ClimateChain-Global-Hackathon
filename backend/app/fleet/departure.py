"""Departure-risk models: how early might this driver unplug?

Every feature for a session on date D uses only that driver's sessions on dates
strictly before D, plus the arrival time already observed at plug-in. Delivered
energy is excluded: it depends on how long the car stayed (future information).

A model returns a *conservative* dwell: the time by which the requested energy
must be delivered. Its coverage (share of drivers still plugged in at that time)
is calibrated on the validation year only; the test year measures it.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FEATURES = ["arrival_h", "weekday", "n_prior", "dwell_median", "dwell_q10", "dwell_q25", "dwell_std",
            "dwell_last5", "departure_median", "departure_q10", "weekday_dwell_median", "days_since_last"]
MIN_HISTORY = 3


def history_features(df):
    """Expanding per-driver features; same-day sessions never see each other."""
    out = {k: np.full(len(df), np.nan) for k in FEATURES}
    out["arrival_h"] = df.arrival_h.to_numpy(dtype=float)
    out["weekday"] = df.weekday.to_numpy(dtype=float)
    out["n_prior"] = np.zeros(len(df))
    order = df.sort_values(["start_utc"]).index
    past = {}  # driver -> list of (date, weekday, dwell, departure_h)
    pending = []  # rows of the current date, committed after the date ends
    current = None
    dates = df.date.to_numpy(); drivers = df.driver.to_numpy()
    for idx in order:
        date = dates[idx]
        if date != current:
            for row in pending:
                past.setdefault(drivers[row], []).append((dates[row], df.at[row, "weekday"], df.at[row, "dwell_h"], df.at[row, "departure_h"]))
            pending = []; current = date
        pending.append(idx)
        driver = drivers[idx]
        history = past.get(driver) if driver != "shared" else None
        if not history:
            continue
        dwell = np.array([h[2] for h in history]); dep = np.array([h[3] for h in history])
        out["n_prior"][idx] = len(history)
        if len(history) < MIN_HISTORY:
            continue
        out["dwell_median"][idx] = np.median(dwell)
        out["dwell_q10"][idx] = np.quantile(dwell, .1)
        out["dwell_q25"][idx] = np.quantile(dwell, .25)
        out["dwell_std"][idx] = dwell.std()
        out["dwell_last5"][idx] = dwell[-5:].mean()
        out["departure_median"][idx] = np.median(dep)
        out["departure_q10"][idx] = np.quantile(dep, .1)
        same = dwell[np.array([h[1] for h in history]) == df.at[idx, "weekday"]]
        if len(same) >= MIN_HISTORY:
            out["weekday_dwell_median"][idx] = np.median(same)
        out["days_since_last"][idx] = min(60, (pd.Timestamp(date) - pd.Timestamp(history[-1][0])).days)
    return pd.DataFrame(out, index=df.index)


class PopulationQuantile:
    """Arrival-hour conditional dwell quantile, no personal history."""
    name = "population"

    def fit(self, df, X, alpha):
        self.alpha = alpha
        bins = np.clip(df.arrival_h.astype(int), 4, 16)
        self.table = df.dwell_h.groupby(bins).quantile(alpha).to_dict()
        self.default = float(df.dwell_h.quantile(alpha))
        return self

    def predict(self, df, X):
        bins = np.clip(df.arrival_h.astype(int), 4, 16)
        return np.array([self.table.get(b, self.default) for b in bins])


class DriverShrinkQuantile:
    """Quantile of the driver's past dwell times mixed with k population pseudo-samples."""
    name = "driver_shrinkage"

    def __init__(self, k=8):
        self.k = k

    def fit(self, df, X, alpha):
        self.alpha = alpha
        self.population = PopulationQuantile().fit(df, X, alpha)
        bins = np.clip(df.arrival_h.astype(int), 4, 16)
        self.samples = {b: np.sort(g.to_numpy()) for b, g in df.dwell_h.groupby(bins)}
        self.all = np.sort(df.dwell_h.to_numpy())
        return self

    def predict(self, df, X, histories=None):
        base = self.population.predict(df, X)
        out = base.copy()
        for i, idx in enumerate(df.index):
            past = histories.get(idx) if histories is not None else None
            if past is None or len(past) < MIN_HISTORY:
                continue
            pop = self.samples.get(int(np.clip(int(df.at[idx, "arrival_h"]), 4, 16)), self.all)
            # Weighted mixture: each personal sample weight 1, population total weight k.
            values = np.concatenate([past, pop])
            weights = np.concatenate([np.ones(len(past)), np.full(len(pop), self.k / len(pop))])
            order = np.argsort(values)
            cumulative = np.cumsum(weights[order]) / weights.sum()
            out[i] = values[order][np.searchsorted(cumulative, self.alpha)]
        return out


class BoostedQuantile:
    """LightGBM quantile regression on personal-history features."""
    name = "lightgbm_quantile"

    def fit(self, df, X, alpha):
        from lightgbm import LGBMRegressor
        self.alpha = alpha
        self.model = LGBMRegressor(objective="quantile", alpha=alpha, n_estimators=300, learning_rate=.03,
                                   num_leaves=15, min_child_samples=80, subsample=.8, subsample_freq=1,
                                   random_state=42, n_jobs=1, deterministic=True, force_col_wise=True, verbosity=-1)
        self.model.fit(X[FEATURES], df.dwell_h)
        return self

    def predict(self, df, X):
        return self.model.predict(X[FEATURES], num_threads=1)


LEVELS = (.02, .05, .1, .2, .35, .5, .7, .9)


class DepartureDistribution:
    """Calibrated quantiles of dwell time -> discrete departure distribution per car.

    Each level's model is fitted on the training years. A per-level conformal
    shift, from a later calibration window only, makes P(dwell < q_k) ~= level_k.
    Quantiles are sorted to remove crossing. `base` selects the learner, so the
    personal-history model and the population ablation share one interface.
    """

    def __init__(self, base="lightgbm", levels=LEVELS):
        self.base, self.levels = base, tuple(levels)

    def fit(self, df, X):
        make = BoostedQuantile if self.base == "lightgbm" else PopulationQuantile
        self.models = [make().fit(df, X, level) for level in self.levels]
        return self

    def raw(self, df, X):
        # Monotone rearrangement first: separately fitted levels can cross.
        return np.sort(np.column_stack([m.predict(df, X) for m in self.models]), axis=1)

    def scores(self, df, X):
        return self.raw(df, X) - df.dwell_h.to_numpy()[:, None]

    def calibrate(self, df, X):
        # shift_k: P(actual >= q_k - shift_k) = 1 - level_k on the calibration window.
        scores = self.scores(df, X)
        self.shifts = np.array([float(np.quantile(scores[:, k], 1 - level, method="higher"))
                                for k, level in enumerate(self.levels)])
        return self

    def quantiles(self, df, X, shifts=None):
        shifts = self.shifts if shifts is None else shifts
        return np.sort(np.maximum(self.raw(df, X) - shifts, 0.0), axis=1)

    def rolling_shifts(self, df, X, window_days=56, minimum=300):
        """Per-date shifts from realised departures in the previous window only (drift-aware).

        Falls back to the fixed calibration-window shifts when too few past sessions exist.
        """
        scores = self.scores(df, X); dates = pd.to_datetime(df.date).to_numpy()
        out = {}
        for date in np.unique(dates):
            mask = (dates < date) & (dates >= date - np.timedelta64(window_days, "D"))
            if mask.sum() < minimum:
                out[pd.Timestamp(date).strftime("%Y-%m-%d")] = self.shifts; continue
            out[pd.Timestamp(date).strftime("%Y-%m-%d")] = np.array(
                [float(np.quantile(scores[mask, k], 1 - level, method="higher")) for k, level in enumerate(self.levels)])
        return out

    def risk_points(self, arrival_h, quantiles):
        """((departure hour, probability), ...), conservative within each band.

        Mass below the lowest level sits one half-hour after plug-in (the earliest
        possible unplug the controller can act on); mass between consecutive
        levels sits at the lower quantile; the upper tail sits at the top level.
        """
        edges = list(self.levels) + [1.0]
        points = [(float(arrival_h + .5), float(edges[0]))]
        points += [(float(arrival_h + q), float(edges[k + 1] - edges[k])) for k, q in enumerate(quantiles)]
        return tuple(points)

    def coverage(self, df, X):
        q = self.quantiles(df, X); actual = df.dwell_h.to_numpy()
        return {f"{level:.2f}": float(np.mean(actual < q[:, k])) for k, level in enumerate(self.levels)}


def driver_histories(df):
    """Per-row arrays of the driver's dwell times on strictly earlier dates."""
    by_driver = {}; result = {}
    for date, group in df.sort_values("start_utc").groupby("date", sort=True):
        for idx, driver in zip(group.index, group.driver):
            if driver != "shared" and driver in by_driver:
                result[idx] = np.array(by_driver[driver])
        for driver, dwell in zip(group.driver, group.dwell_h):
            if driver != "shared":
                by_driver.setdefault(driver, []).append(dwell)
    return result


def conformal_shift(predicted, actual, coverage):
    """Additive shift so that `coverage` of sessions are still present at predicted-shift."""
    scores = predicted - actual  # positive means the driver left before the prediction
    return float(np.quantile(scores, coverage, method="higher"))


def rolling_shifts(dates, scores, coverage, window_days=56, minimum=200, fallback=0.0):
    """Per-date shift from realised scores on the previous `window_days` only.

    A departure is observed by the end of its own day, so a decision on date D can
    use every session dated before D. Returns {date: shift}.
    """
    frame = pd.DataFrame({"date": pd.to_datetime(dates), "score": scores}).sort_values("date")
    out = {}
    for date in sorted(frame.date.unique()):
        past = frame.loc[(frame.date < date) & (frame.date >= date - pd.Timedelta(days=window_days)), "score"]
        out[pd.Timestamp(date).strftime("%Y-%m-%d")] = float(np.quantile(past, coverage, method="higher")) if len(past) >= minimum else fallback
    return out
