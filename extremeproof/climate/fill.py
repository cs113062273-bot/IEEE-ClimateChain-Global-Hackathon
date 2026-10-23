"""Estimate missing station TX from ERA5: the pre-agreed gap-filling rules.

A fill method is fitted only on days where both the station and ERA5 have
values, inside a declared fit period that ends before the observation year,
so a fill can never be tuned on the season it is used for.

Methods (all deterministic, standard library only):
  none                  missing days stay missing (they break spells)
  era5_raw              use the ERA5 value as-is (keeps ERA5's bias)
  era5_monthly_linear   per calendar month, station = a + b * ERA5 (least squares)
  era5_quantile_map     per calendar month, map ERA5's empirical quantile onto the
                        station's (Hyndman-Fan type-8 quantiles at 1..99 %)
"""
from .engine import quantile

METHODS = ("none", "era5_raw", "era5_monthly_linear", "era5_quantile_map")
QM_LEVELS = [i / 100 for i in range(1, 100)]


def pairs_in(station, era5, start, end):
    return [(d, station[d], era5[d]) for d in station if start <= d <= end and d in era5]


def fit(method, station, era5, start, end):
    """Return a JSON-serialisable parameter dict for the fill method."""
    return fit_pairs(method, pairs_in(station, era5, start, end))


def fit_pairs(method, pairs):
    """Fit from (date, station_value, era5_value) triples (possibly pooled over stations)."""
    if method in ("none", "era5_raw"):
        return {"method": method}
    by_month = {m: [(s, e) for d, s, e in pairs if d.month == m] for m in range(1, 13)}
    if method == "era5_monthly_linear":
        params = {}
        for m, xy in by_month.items():
            if len(xy) < 30:
                raise ValueError(f"too few paired days in month {m}: {len(xy)}")
            n = len(xy)
            mx = sum(e for _, e in xy) / n
            my = sum(s for s, _ in xy) / n
            sxx = sum((e - mx) ** 2 for _, e in xy)
            sxy = sum((e - mx) * (s - my) for s, e in xy)
            b = sxy / sxx
            params[str(m)] = {"a": my - b * mx, "b": b, "n": n}
        return {"method": method, "months": params}
    if method == "era5_quantile_map":
        params = {}
        for m, xy in by_month.items():
            if len(xy) < 30:
                raise ValueError(f"too few paired days in month {m}: {len(xy)}")
            st = [s for s, _ in xy]
            er = [e for _, e in xy]
            params[str(m)] = {"era5_q": [quantile(er, q) for q in QM_LEVELS],
                              "station_q": [quantile(st, q) for q in QM_LEVELS], "n": len(xy)}
        return {"method": method, "months": params}
    raise ValueError(f"unknown fill method {method}")


def predict(params, d, era5_value):
    method = params["method"]
    if method == "none" or era5_value is None:
        return None
    if method == "era5_raw":
        return era5_value
    p = params["months"][str(d.month)]
    if method == "era5_monthly_linear":
        return p["a"] + p["b"] * era5_value
    if method == "era5_quantile_map":
        return _interp(era5_value, p["era5_q"], p["station_q"])
    raise ValueError(f"unknown fill method {method}")


def _interp(x, xs, ys):
    """Piecewise-linear map; beyond the 1st/99th percentile, shift by the end offset."""
    if x <= xs[0]:
        return ys[0] + (x - xs[0])
    if x >= xs[-1]:
        return ys[-1] + (x - xs[-1])
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    if xs[hi] == xs[lo]:
        return ys[lo]
    return ys[lo] + (ys[hi] - ys[lo]) * (x - xs[lo]) / (xs[hi] - xs[lo])
