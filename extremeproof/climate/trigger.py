"""Trigger specifications and provider verdicts.

A spec is the rule three parties sign. It is canonical JSON containing only
strings, integers, booleans, lists and objects (no floats), so Python and the
browser hash it identically; its sha256 is what the contract stores.

The spec pins only what exists when it is signed: each source's history up to
31 December before the observation year (the base period and the gap-fill fit
period end there). For the observation year it names where the data will come
from; it cannot hash data that do not exist yet.

``evaluate(spec, source_id, season=...)`` is what one data provider runs after
the season: it checks the pinned history against the spec, takes the
observation-year data it fetched, applies the rule, and returns an evidence
bundle that records the sha256 of every file it used. The provider's on-chain
report carries the digest of that evidence, which binds it to those bytes.
Real numbers in the bundle are written as Python ``repr`` strings (shortest
round-trip), keeping it float-free too.

A provider whose data are insufficient under the agreed limits returns
``outcome = None`` (abstain) with a reason. Abstaining is never silently turned
into "not met": the contract then lacks a quorum and the dispute path applies.

The contract compares readings with thresholds itself, so both are integers in
thousandths of a degree: each source's daily thresholds for the season (its
"normal") are computed from the pinned history and rounded DOWN, then signed into
the spec; readings are rounded half up (both after rounding to a millionth, so
floating-point noise between implementations cannot move them). Station and ERA5 readings come in tenths,
so for them the integer comparison is exactly the real-number one; only a
gap-filled value within half a thousandth of its threshold could differ.
"""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from pathlib import Path

from . import archive as A
from . import engine as E
from . import fill as F
from .sources import parse_ghcn, parse_open_meteo

SPEC_SCHEMA = "extremeproof.trigger.v2"
EVIDENCE_SCHEMA = "extremeproof.evidence.v2"
ROOT = Path(__file__).resolve().parents[1]  # extremeproof/
LOCAL_TZ = timezone(timedelta(hours=3))  # Europe/Istanbul (permanent UTC+3), the zone of the ERA5 daily data
DAY = 86400
REPORT_DAYS, DISPUTE_DAYS = 14, 30
NO_THRESHOLD = 2**31 - 1  # a calendar day without a threshold is never "unusually hot" (int32 max on chain)
MICRO = Decimal("0.000001")
PUBLICATION_LAG_DAYS = 5  # during the season a provider can see data up to this many days ago
ON_DISPUTE = ("refund", "pay")  # index = TriggerAgreement.Fallback
VERDICT = {True: 1, False: 2, None: 3}  # TriggerAgreement.Verdict: Met, NotMet, Abstain
FULL_BPS = 10000
# A graded ladder relative to the minimum spell: +0 days 40 %, +3 days 70 %, +6 days 100 %.
GRADED_STEPS = ((0, 4000), (3, 7000), (6, 10000))


def _micro(x):
    # First to a millionth of a degree: two implementations of the same percentile differ by ~1e-12,
    # which must not decide which side of a thousandth a threshold lands on.
    return Decimal(repr(float(x))).quantize(MICRO, ROUND_HALF_UP)


def reading_mdegc(x):
    """A reading in thousandths of a degree, rounded half up (exact for data in tenths)."""
    return None if x is None else int((_micro(x) * 1000).to_integral_value(ROUND_HALF_UP))


def threshold_mdegc(x):
    """A threshold in thousandths of a degree, rounded down, so a reading in tenths exceeds it exactly when it exceeds the real value."""
    return NO_THRESHOLD if x is None else int((_micro(x) * 1000).to_integral_value(ROUND_FLOOR))


def season_days(year, season):
    return list(E.daterange(md(year, season[0]), md(year, season[1])))


def season_normal(src, rule, year, root=ROOT):
    """The daily thresholds signed for one source: from its pinned history alone, so they exist before
    the season. None when the history covers too little of the base period to define a normal."""
    texts = [pinned_history(src, root).decode("utf-8")]
    series = parse_ghcn(texts, "TMAX")[0] if src["kind"] == "ghcn_daily" else parse_open_meteo(texts, "temperature_2m_max")[0]
    b0, b1 = d(rule["base_period"][0]), d(rule["base_period"][1])
    present, total = E.completeness(series, b0, b1)
    if present * 1000 // total < rule["min_base_coverage_permille"]:
        return None
    th = E.percentile_doy(series, b0, b1, rule["percentile"], rule["percentile_window_days"])
    return [threshold_mdegc(th.get(E.doy(day))) for day in season_days(year, rule["season"])]


def payout_ladder(min_spell_days, payout="flat", steps=None):
    """[[min days, basis points], ...]; "flat" is the classic all-or-nothing trigger. ``steps`` are the
    parties' own graded rungs as [days beyond the minimum spell, basis points]."""
    if payout == "flat":
        return [[min_spell_days, FULL_BPS]]
    if payout == "graded":
        return [[min_spell_days + d, bps] for d, bps in (steps or GRADED_STEPS)]
    raise ValueError("payout must be flat or graded")


def share_bps(ladder, spell):
    """Share of the deposit the ladder pays for a spell of ``spell`` days (TriggerAgreement.payoutFor)."""
    out = 0
    for days, bps in ladder:
        if spell >= days:
            out = bps
    return out


def contract_timing(year, season=("06-01", "09-30")):
    """Unix times the contract uses: lock before the season starts; reports after it ends (local midnight)."""
    m0, d0 = map(int, season[0].split("-"))
    m1, d1 = map(int, season[1].split("-"))
    start = int(datetime(year, m0, d0, tzinfo=LOCAL_TZ).timestamp())
    end = int((datetime(year, m1, d1, tzinfo=LOCAL_TZ) + timedelta(days=1)).timestamp())
    return {"window_start": start, "window_end": end, "report_deadline": end + REPORT_DAYS * DAY,
            "dispute_window": DISPUTE_DAYS * DAY}


class SpecError(ValueError):
    pass


class SourceHashMismatch(ValueError):
    pass


def canonical(obj):
    _no_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _no_floats(o, path="$"):
    if isinstance(o, float):
        raise SpecError(f"float at {path}; use integers or strings")
    if isinstance(o, dict):
        for k, v in o.items():
            if not isinstance(k, str):
                raise SpecError(f"non-string key at {path}")
            _no_floats(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _no_floats(v, f"{path}[{i}]")


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def spec_hash(spec):
    return "0x" + sha256_hex(canonical(spec))


def evidence_digest(evidence):
    return "0x" + sha256_hex(canonical(evidence))


def num(x):
    return None if x is None else repr(float(x))


def d(s):
    y, m, dd = s.split("-")
    return date(int(y), int(m), int(dd))


def md(year, s):
    m, dd = s.split("-")
    return date(year, int(m), int(dd))


def validate(spec):
    if spec.get("schema") != SPEC_SCHEMA:
        raise SpecError("unknown schema")
    canonical(spec)
    r = spec["rule"]
    if r.get("kind") != "heat_spell" or r.get("variable") != "TX":
        raise SpecError("only heat_spell on daily maximum temperature (TX) is implemented")
    b0, b1 = d(r["base_period"][0]), d(r["base_period"][1])
    if not (b0.month == 1 and b0.day == 1 and b1.month == 12 and b1.day == 31 and b1.year - b0.year >= 9):
        raise SpecError("base period must be whole calendar years, at least 10")
    year = spec["observation_year"]
    if year <= b1.year:
        raise SpecError("observation year must be after the base period (in-base years need bootstrapping; backtest only)")
    if not (1 <= r["percentile"] <= 99) or r["percentile_window_days"] % 2 != 1:
        raise SpecError("percentile must be 1..99 and the window odd")
    s0, s1 = md(year, r["season"][0]), md(year, r["season"][1])
    if s1 < s0 or r["min_spell_days"] < 1:
        raise SpecError("bad season or spell length")
    ids = [s["id"] for s in spec["sources"]]
    if len(ids) != len(set(ids)) or len(ids) < 2:
        raise SpecError("need at least two sources with unique ids")
    for s in spec["sources"]:
        h, sd = s.get("history") or {}, s.get("season_data") or {}
        # Signed before the season: pin what exists (history), name where the rest will come from.
        if h.get("through") != f"{year - 1}-12-31" or not h.get("file") or not h.get("sha256"):
            raise SpecError("each source must pin its history up to 31 December before the observation year")
        if sd.get("from") != f"{year}-01-01" or sd.get("to") != f"{year}-{r['season'][1]}" or not sd.get("url"):
            raise SpecError("each source must name where its observation-year data will be fetched after the season")
        if "sha256" in sd:
            raise SpecError("observation-year data cannot be pinned before the season")
        n = s.get("season_normal_mdegc", "absent")
        if n is not None and (not isinstance(n, list) or len(n) != len(season_days(year, r["season"]))
                              or not all(isinstance(x, int) and -2**31 <= x < 2**31 for x in n)):
            raise SpecError("each source must sign its daily thresholds for the season (int32 thousandths of a degree) or null")
        f = s.get("fill")
        if f:
            if f["method"] not in F.METHODS:
                raise SpecError(f"unknown fill method {f['method']}")
            if f["from"] not in ids or f["from"] == s["id"]:
                raise SpecError("fill must come from another declared source")
            if d(f["fit_period"][1]) >= date(year, 1, 1):
                raise SpecError("fill must be fitted only on data before the observation year")
    p = spec.get("purpose")
    if p is not None:  # optional: how often the parties meant it to pay, and the calibration they saw
        n = p.get("target_return_period_summers")
        if not isinstance(n, int) or not 1 < n <= 100:
            raise SpecError("purpose.target_return_period_summers must be an integer 2..100")
        if not all(isinstance(p.get(k), int) and 0 <= p[k] <= p.get("summers", -1)
                   for k in ("final_pays", "agreement_pays", "disputes_records_disagree", "disputes_too_little_data")):
            raise SpecError("purpose counts must be integers within the calibration window")
        if p["final_pays"] < p["agreement_pays"]:
            raise SpecError("purpose.final_pays counts payments by agreement plus by fallback, so it cannot be smaller")
        # The target means final payments under the signed fallback, so both must name the same fallback.
        if p.get("on_dispute") not in ON_DISPUTE or (spec.get("settlement") and p["on_dispute"] != spec["settlement"].get("on_dispute")):
            raise SpecError("purpose.on_dispute must equal the signed dispute fallback")
    st = spec.get("settlement")
    if st is not None:
        if st.get("on_dispute") not in ON_DISPUTE:
            raise SpecError("on_dispute must be refund or pay")
        q, n = st.get("quorum"), st.get("providers")
        if n != len(ids) or not (1 <= q <= n and 2 * q > n):
            raise SpecError("quorum must be a strict majority of one provider per source")
        if not isinstance(st.get("amount_cents"), int) or st["amount_cents"] <= 0:
            raise SpecError("amount must be a positive integer number of cents")
        if st.get("timing") != contract_timing(year, r["season"]):
            raise SpecError("contract windows do not match the observation season")
        lad = st.get("payout_ladder")
        if (not isinstance(lad, list) or not 1 <= len(lad) <= 8 or lad[0][0] != r["min_spell_days"] or lad[-1][1] != FULL_BPS
                or any(not (isinstance(d, int) and isinstance(b, int) and d > 0 and b > 0) for d, b in lad)
                or any(lad[i][0] <= lad[i - 1][0] or lad[i][1] <= lad[i - 1][1] for i in range(1, len(lad)))):
            raise SpecError("payout_ladder must start at the minimum spell, rise in days and share, and end at 100 %")
        pa = st.get("provider_addresses")
        if pa is not None and (set(pa) != set(ids) or len(set(pa.values())) != len(pa)):
            raise SpecError("each data source needs its own provider address")
    return True


def pinned_history(src, root=ROOT):
    """The history bytes the spec pins, checked against its sha256."""
    data = A.read_logical(root, src["history"]["file"])
    got = sha256_hex(data)
    if got != src["history"]["sha256"]:
        raise SourceHashMismatch(f"{src['id']}: {src['history']['file']} sha256 {got} != spec {src['history']['sha256']}")
    return data


def load_source(src, observation, root=ROOT):
    """One series from the pinned history plus the observation-year bytes a provider fetched."""
    texts = [pinned_history(src, root).decode("utf-8"), observation.decode("utf-8")]
    if src["kind"] == "ghcn_daily":
        series, excluded = parse_ghcn(texts, "TMAX")
        return series, {"excluded_by_qc": len(excluded)}
    if src["kind"] == "open_meteo":
        series, meta = parse_open_meteo(texts, "temperature_2m_max")
        return series, {"grid_lat": num(meta["latitude"]), "grid_lon": num(meta["longitude"])}
    raise SpecError(f"unknown source kind {src['kind']}")


def needed_sources(spec, source_id):
    """Ids of the sources a provider must fetch: its own, plus the one its gap filling uses."""
    src = next(s for s in spec["sources"] if s["id"] == source_id)
    f = src.get("fill")
    return [source_id] + ([f["from"]] if f and f["method"] != "none" else [])


def fetch_observations(spec, source_id, root=ROOT, through=None):
    """Simulated fetch of every observation-year file a provider needs (see archive.py); ``through``
    limits it to the days already published during the season."""
    by_id = {s["id"]: s for s in spec["sources"]}
    return {sid: A.fetch_season(root, by_id[sid], spec["observation_year"], through) for sid in needed_sources(spec, source_id)}


def evaluate(spec, source_id, season=None, root=ROOT, through=None):
    """``season`` maps source id -> observation-year bytes the provider fetched; None fetches them (simulated).

    ``through`` (a date inside the season) evaluates an interim report: the season so far, with the
    agreed data limits applied to the days so far. A spell already seen cannot shrink later.
    """
    validate(spec)
    if season is None:
        season = fetch_observations(spec, source_id, root, through)
    by_id = {s["id"]: s for s in spec["sources"]}
    src = by_id[source_id]
    r = spec["rule"]
    year = spec["observation_year"]
    series, src_meta = load_source(src, season[source_id], root)
    b0, b1 = d(r["base_period"][0]), d(r["base_period"][1])
    present, total = E.completeness(series, b0, b1)
    coverage = present * 1000 // total
    ev = {
        "schema": EVIDENCE_SCHEMA,
        "spec_hash": spec_hash(spec),
        "provider_source": source_id,
        "history": {sid: {"file": by_id[sid]["history"]["file"], "sha256": by_id[sid]["history"]["sha256"]}
                    for sid in needed_sources(spec, source_id)},
        # The observation-year bytes this provider fetched after the season. The on-chain report
        # carries this evidence's digest, so it binds the provider to exactly these files.
        "observations": {sid: {"file": f"observations/{source_id}/{A.season_name(by_id[sid]['kind'], by_id[sid]['station'], year)}",
                               "sha256": sha256_hex(season[sid]), "url": by_id[sid]["season_data"]["url"]}
                         for sid in needed_sources(spec, source_id)},
        "source_meta": src_meta,
        "observation_year": year,
        "base": {"present_days": present, "total_days": total, "coverage_permille": coverage},
    }
    if through is not None:
        ev["interim_through"] = through.isoformat()
    if coverage < r["min_base_coverage_permille"]:
        if src.get("season_normal_mdegc") is not None:
            raise SpecError(f"{source_id}: a normal is signed but the history cannot define one")
        return _abstain(ev, "base_period_coverage_below_agreed_minimum")

    th = E.percentile_doy(series, b0, b1, r["percentile"], r["percentile_window_days"])
    normal = [threshold_mdegc(th.get(E.doy(day))) for day in season_days(year, r["season"])]
    if normal != src["season_normal_mdegc"]:
        raise SpecError(f"{source_id}: the signed daily thresholds differ from the ones the pinned history gives")
    ev["season_normal_mdegc"] = normal
    fill_spec = src.get("fill")
    params, fill_series = {"method": "none"}, {}
    if fill_spec and fill_spec["method"] != "none":
        other = by_id[fill_spec["from"]]
        fill_series, _ = load_source(other, season[other["id"]], root)
        params = F.fit(fill_spec["method"], series, fill_series, d(fill_spec["fit_period"][0]), d(fill_spec["fit_period"][1]))
    ev["fill"] = {"method": params["method"], "params": _stringify(params)}

    days, missing, filled = [], 0, 0
    flags = []
    season_end = md(year, r["season"][1]) if through is None else min(md(year, r["season"][1]), through)
    for day in E.daterange(md(year, r["season"][0]), season_end):
        v, how = series.get(day), "observed"
        if v is None:
            v = F.predict(params, day, fill_series.get(day))
            how = "filled" if v is not None else "missing"
        t = th.get(E.doy(day))
        vm, tm = reading_mdegc(v), threshold_mdegc(t)
        exc = vm is not None and vm > tm  # the comparison the contract makes
        missing += how == "missing"
        filled += how == "filled"
        flags.append(exc)
        days.append({"date": day.isoformat(), "tx": num(v), "threshold": num(t), "v": vm, "t": tm, "status": how, "exceeds": exc})
    runs = _spells(days, flags)
    longest = max((x["days"] for x in runs), default=0)
    ev["season"] = {"days": days, "missing_days": missing, "filled_days": filled, "spells": runs, "longest_spell": longest}
    if missing > r["max_missing_days"]:
        return _abstain(ev, "too_many_missing_days_in_season")
    if filled > r["max_filled_days"]:
        return _abstain(ev, "too_many_filled_days_in_season")
    # Interim: a spell already seen stands, but only if filling the rest of the season could not break
    # the agreed fill limit; otherwise the provider waits for the final report.
    remaining = (md(year, r["season"][1]) - season_end).days
    if through is not None and filled + remaining > r["max_filled_days"]:
        return _abstain(ev, "fill_limit_could_still_be_exceeded")
    ev["outcome"] = longest >= r["min_spell_days"]
    ev["reason"] = "spell_meets_minimum" if ev["outcome"] else "no_spell_long_enough"
    return ev


def _abstain(ev, reason):
    ev["outcome"] = None
    ev["reason"] = reason
    return ev


def _spells(days, flags):
    out, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append({"start": days[start]["date"], "end": days[i - 1]["date"], "days": i - start})
            start = None
    return out


def _stringify(o):
    if isinstance(o, float):
        return repr(o)
    if isinstance(o, dict):
        return {k: _stringify(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_stringify(v) for v in o]
    return o
