"""Percentile-based temperature-extreme indices, standard library only.

The definitions follow ETCCDI (Zhang et al. 2011; list of 27 indices at
https://etccdi.pacificclimate.org/list_27_indices.shtml) and reproduce the
numerical conventions of xclim 0.58, which the test-suite uses as an
independent reference implementation:

* calendar-day percentile from a centred 5-day window over the base period,
  Hyndman & Fan (1996) type 8 sample quantile (alpha = beta = 1/3);
* thresholds are computed for day-of-year 1..365 and stretched linearly onto
  1..366 (xclim ``adjust_doy_calendar``);
* exceedance is strict (TX > threshold); a missing value never exceeds;
* years inside the base period are bootstrapped (Zhang et al. 2005): the year
  is replaced in turn by every other base year, thresholds are recomputed and
  the index is averaged over the replicates.

A series is a dict {datetime.date: float | None}. Missing days may be absent
or None; callers decide separately (see ``completeness``) whether a period has
enough data to be used at all.
"""
from datetime import date, timedelta
import math

ALPHA = BETA = 1.0 / 3.0


def daterange(start, end):
    d = start
    one = timedelta(days=1)
    while d <= end:
        yield d
        d += one


def doy(d):
    return d.timetuple().tm_yday


def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def quantile(values, q):
    """Type-8 sample quantile of the non-missing values, as xclim ``_nan_quantile``."""
    v = sorted(x for x in values if x is not None)
    n = len(v)
    if n == 0:
        return None
    if n == 1:
        return v[0]
    vi = n * q + (ALPHA + q * (1 - ALPHA - BETA)) - 1
    if vi >= n - 1:
        return v[-1]
    if vi < 0:
        return v[0]
    lo = math.floor(vi)
    g = vi - lo
    a, b = v[lo], v[lo + 1]
    if g >= 0.5:
        return b - (b - a) * (1 - g)
    return a + (b - a) * g


def percentile_doy(series, base_start, base_end, per=90.0, window=5, doy_range=None):
    """Calendar-day percentile thresholds {doy 1..366: value | None} over the base period.

    ``doy_range=(a, b)`` computes only what is needed for target days a..b
    (a speed-up for seasonal indices); other days come back as None.
    """
    dates = list(daterange(base_start, base_end))
    vals = [series.get(d) for d in dates]
    half = window // 2
    groups = {}
    n = len(vals)
    lo_doy, hi_doy = (doy_range[0] - 3, doy_range[1] + 3) if doy_range else (0, 367)
    for i, d in enumerate(dates):
        k = doy(d)
        if lo_doy <= k <= hi_doy:
            lo, hi = max(0, i - half), min(n, i + half + 1)
            groups.setdefault(k, []).extend(vals[lo:hi])
    q = per / 100.0
    raw = {k: quantile(g, q) for k, g in groups.items()}
    leap_in_base = any(is_leap(y) for y in range(base_start.year, base_end.year + 1))
    if not leap_in_base:
        return raw
    return _stretch_365_to_366([raw.get(k) for k in range(1, 366)])


def _stretch_365_to_366(src):
    """xclim ``_interpolate_doy_calendar``: fill gaps linearly, then map 365 points onto 1..366."""
    src = _interpolate_na(src)
    pos = [1 + i * (366 - 1) / (365 - 1) for i in range(365)]
    out = {}
    j = 0
    for t in range(1, 367):
        while j < 363 and pos[j + 1] < t:
            j += 1
        x0, x1 = pos[j], pos[j + 1]
        y0, y1 = src[j], src[j + 1]
        if t == x0:
            out[t] = y0
        elif t == x1:
            out[t] = y1
        elif y0 is None or y1 is None:
            out[t] = None
        else:
            out[t] = y0 + (y1 - y0) * (t - x0) / (x1 - x0)
    return out


def _interpolate_na(v):
    """Linear interpolation over interior gaps; leading/trailing gaps stay missing."""
    v = list(v)
    known = [i for i, x in enumerate(v) if x is not None]
    for a, b in zip(known, known[1:]):
        for i in range(a + 1, b):
            v[i] = v[a] + (v[b] - v[a]) * (i - a) / (b - a)
    return v


def exceeds(series, thresholds, d):
    x = series.get(d)
    t = thresholds.get(doy(d))
    return x is not None and t is not None and x > t


def runs(flags):
    """Lengths of consecutive True runs in a list of booleans."""
    out, cur = [], 0
    for f in flags:
        if f:
            cur += 1
        else:
            if cur:
                out.append(cur)
            cur = 0
    if cur:
        out.append(cur)
    return out


# --- indices for one year, given thresholds -------------------------------

def tx90p_days(series, thresholds, year):
    return sum(exceeds(series, thresholds, d) for d in daterange(date(year, 1, 1), date(year, 12, 31)))


def wsdi_days(series, thresholds, year, window=6):
    flags = [exceeds(series, thresholds, d) for d in daterange(date(year, 1, 1), date(year, 12, 31))]
    return sum(r for r in runs(flags) if r >= window)


def season_dates(year, season):
    (m0, d0), (m1, d1) = season
    return list(daterange(date(year, m0, d0), date(year, m1, d1)))


def longest_spell(series, thresholds, year, season):
    flags = [exceeds(series, thresholds, d) for d in season_dates(year, season)]
    return max(runs(flags), default=0)


# --- bootstrap ---------------------------------------------------------------

def replace_year(series, target, source):
    """Copy of ``series`` with calendar year ``target`` replaced by year ``source``.

    Mirrors xclim ``build_bootstrap_year_da``: month/day alignment, a source
    leap day is dropped for a non-leap target, and a leap target gets a missing
    Feb 29 when the source year has none.
    """
    out = {d: v for d, v in series.items() if d.year != target}
    for d in daterange(date(target, 1, 1), date(target, 12, 31)):
        if d.month == 2 and d.day == 29 and not is_leap(source):
            out[d] = None
        else:
            out[d] = series.get(date(source, d.month, d.day))
    return out


def bootstrapped(series, base_start, base_end, year, index_fn, per=90.0, window=5):
    """Average of ``index_fn(thresholds)`` over the Zhang et al. (2005) replicates for an in-base year."""
    others = [y for y in range(base_start.year, base_end.year + 1) if y != year]
    vals = []
    for s in others:
        th = percentile_doy(replace_year(series, year, s), base_start, base_end, per, window)
        vals.append(index_fn(th))
    return vals


def in_base(year, base_start, base_end):
    return base_start.year <= year <= base_end.year


# --- data sufficiency ---------------------------------------------------------

def completeness(series, start, end):
    total = present = 0
    for d in daterange(start, end):
        total += 1
        present += series.get(d) is not None
    return present, total
