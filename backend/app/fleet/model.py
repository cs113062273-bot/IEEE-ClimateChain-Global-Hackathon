"""Frozen departure-risk model shared by the evaluation and the live product.

Fit on 2021-2022 sessions, conformal shifts from 2023 H1. The cache lives in
gitignored data/processed because it is derived from CC BY-NC-SA session data.
"""
from __future__ import annotations
import hashlib
import pickle
from functools import lru_cache
import numpy as np
import pandas as pd
from .sessions import ROOT, load_sessions, raw_sha256
from .departure import DepartureDistribution, history_features

CACHE = ROOT / "data/processed/carpark/departure_model.pkl"
FIT = ("2021-01-01", "2023-01-01")
CALIBRATE = ("2023-01-01", "2023-07-01")
MODEL_VERSION = "departure-risk-lightgbm-v1"


def _window(df, span):
    return ((df.date >= span[0]) & (df.date < span[1])).to_numpy()


@lru_cache(maxsize=1)
def frozen():
    """(models by base, features for every session, sessions, metadata)."""
    df, quality = load_sessions()
    source = raw_sha256()
    X = history_features(df)
    if CACHE.exists():
        cached = pickle.loads(CACHE.read_bytes())  # trusted local artefact written below
        if cached.get("source_sha256") == source and cached.get("version") == MODEL_VERSION:
            return cached["models"], X, df, cached["meta"]
    fit, cal = _window(df, FIT), _window(df, CALIBRATE)
    models = {base: DepartureDistribution(base).fit(df[fit], X[fit]).calibrate(df[cal], X[cal])
              for base in ("lightgbm", "population")}
    meta = {"version": MODEL_VERSION, "source_sha256": source, "fit_window": FIT, "calibration_window": CALIBRATE,
            "levels": list(models["lightgbm"].levels), "fit_rows": int(fit.sum()), "calibration_rows": int(cal.sum()),
            "shifts_h": {b: [float(x) for x in m.shifts] for b, m in models.items()}, "quality": quality}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps({"version": MODEL_VERSION, "source_sha256": source, "models": models, "meta": meta}))
    return models, X, df, meta


@lru_cache(maxsize=2)
def quantile_table(base="lightgbm"):
    models, X, df, _ = frozen()
    return pd.DataFrame(models[base].quantiles(df, X), index=df.session_id, columns=models[base].levels)


@lru_cache(maxsize=1)
def history_counts():
    """Prior sessions per session (driver history visible at plug-in), keyed by session id."""
    _, X, df, _ = frozen()
    return dict(zip(df.session_id, X.n_prior.astype(int)))


def promises(sessions, base="lightgbm", level=.2):
    """Decision-time deliver-by hours and risk points for the given sessions."""
    models, *_ = frozen()
    q = quantile_table(base).loc[sessions.session_id].to_numpy()
    arrival = sessions.arrival_h.to_numpy()
    k = list(models[base].levels).index(level)
    risks = [models[base].risk_points(a, row) for a, row in zip(arrival, q)]
    return arrival + q[:, k], risks, q


def model_fingerprint():
    _, _, _, meta = frozen()
    return hashlib.sha256(repr(sorted(meta.items())).encode()).hexdigest()
