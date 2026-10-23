#!/usr/bin/env python3
"""ExtremeProof independent verifier. Python 3.9+ standard library only.

Recomputes a heat-trigger verdict from raw climate data and checks it against
what the parties signed and what the providers put on chain. It deliberately
shares no code with the ExtremeProof engine: percentiles, gap filling, spell
detection, canonical hashing and contract reads are implemented
again here, so a mistake in one implementation shows up as a disagreement.

    python verify.py BUNDLE_DIR_OR_ZIP [--rpc http://127.0.0.1:8545] [--refetch] [--json]

Checks, in order:
  1. the spec's sha256 equals the spec hash the three parties approved on chain,
     and the terms the contract executes (amount, quorum, dispute fallback,
     windows, parties, token, provider per data source) equal the signed spec;
  2. the spec pins only what existed before the season (history up to the end
     of the previous year, before the lock deadline) and every history file in
     the bundle has the pinned sha256;
  3. every provider listed on chain is accounted for: its posted readings (and the
     verdict the contract computed from them) must come with its evidence, whose
     sha256 equals the digest on chain; a provider that never posted is shown as absent;
  4. the observation-year files each provider fetched after the season hash to
     the values in its evidence, i.e. the provider was bound to exactly these
     bytes when it reported; two providers that fetched the same source got
     the same values;
  5. each verdict, longest spell, daily value and threshold is recomputed from
     the pinned history, the fetched observations and the spec alone; the signed
     daily thresholds and their on-chain fingerprint equal the recomputed normal;
     the readings on chain (the contract's day log) are exactly the recomputed
     days; an abstention must be justified by the data;
  6. the settlement follows from the reported verdicts and the quorum, or for a
     dispute from a unanimous vote of the three parties or the signed fallback.

With --refetch, each observation-year file is also compared, value by value,
with what the publisher serves now. That shows whether the provider's data
match today's publication; it cannot prove what was published on the day the
provider fetched it (publishers revise data).

Exit code 0 when every check passes, 1 otherwise.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import sys
import urllib.request
import zipfile
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

TOL = 1e-6

# ----------------------------------------------------------------------------- hashing


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def keccak256(data):
    """Ethereum Keccak-256 (original padding, not NIST SHA3), used only for ABI selectors."""
    rate = 136
    msg = bytearray(data) + b"\x01"
    while len(msg) % rate:
        msg.append(0)
    msg[-1] |= 0x80
    s = [[0] * 5 for _ in range(5)]
    for off in range(0, len(msg), rate):
        for i in range(rate // 8):
            s[i % 5][i // 5] ^= int.from_bytes(msg[off + 8 * i: off + 8 * i + 8], "little")
        for rc in _RC:
            c = [s[x][0] ^ s[x][1] ^ s[x][2] ^ s[x][3] ^ s[x][4] for x in range(5)]
            dd = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M) for x in range(5)]
            s = [[s[x][y] ^ dd[x] for y in range(5)] for x in range(5)]
            b = [[0] * 5 for _ in range(5)]
            for x in range(5):
                for y in range(5):
                    r = _ROT[x][y]
                    b[y][(2 * x + 3 * y) % 5] = ((s[x][y] << r) | (s[x][y] >> (64 - r))) & _M if r else s[x][y]
            s = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
            s[0][0] ^= rc
    out = b"".join(s[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
    return out


def selector(sig):
    return "0x" + keccak256(sig.encode()).hex()[:8]


# The contract compares integers: thousandths of a degree, thresholds rounded down, readings half up.
INT32_MAX = 2**31 - 1
DAY_STATUS = {"observed": 0, "filled": 1, "missing": 2}


def to_micro(x):
    """Rounded to a millionth first, so floating-point noise (~1e-12) cannot decide the thousandth."""
    return Decimal(repr(float(x))).quantize(Decimal("0.000001"), ROUND_HALF_UP)


def milli_reading(x):
    return None if x is None else int((to_micro(x) * 1000).to_integral_value(ROUND_HALF_UP))


def milli_threshold(x):
    return INT32_MAX if x is None else int((to_micro(x) * 1000).to_integral_value(ROUND_FLOOR))


def normal_fingerprint(values):
    """keccak256(abi.encodePacked(int32[])): every element padded to 32 bytes; zero for no normal."""
    if values is None:
        return "0x" + "00" * 32
    return "0x" + keccak256(b"".join(v.to_bytes(32, "big", signed=True) for v in values)).hex()


def day_log(days):
    """SeasonRecord.dayLog: keccak256(previous log ++ int32 reading ++ uint8 status) for every posted day."""
    log = b"\0" * 32
    for x in days:
        v = x["v"] if x["v"] is not None else 0
        log = keccak256(log + v.to_bytes(4, "big", signed=True) + bytes([DAY_STATUS[x["status"]]]))
    return "0x" + log.hex()


# ----------------------------------------------------------------------------- data


def parse_day(s):
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def read_ghcn_tmax(texts):
    """TMAX from one or more GHCN-Daily CSVs read as one record (history, then the season fetch)."""
    vals, seen = {}, set()
    for row in (r for t in texts for r in csv.DictReader(io.StringIO(t))):
        raw = (row.get("TMAX") or "").strip()
        if not raw:
            continue
        day = parse_day(row["DATE"])
        q = (row.get("TMAX_ATTRIBUTES") or "").split(",")
        v = int(raw) / 10.0
        if day in seen:
            vals.pop(day, None)
            continue
        seen.add(day)
        if (len(q) > 1 and q[1].strip()) or v < -50.0 or v > 60.0:
            continue
        vals[day] = v
    # remove runs of 10+ identical consecutive values (stuck sensor)
    days = sorted(vals)
    i = 0
    while i < len(days):
        j = i
        while j + 1 < len(days) and days[j + 1] - days[j] == timedelta(days=1) and vals[days[j + 1]] == vals[days[i]]:
            j += 1
        if j - i >= 9:
            for k in days[i:j + 1]:
                del vals[k]
        i = j + 1
    return vals


def read_open_meteo_tmax(texts):
    out = {}
    for text in texts:
        doc = json.loads(text)
        out.update({parse_day(t): float(v) for t, v in zip(doc["daily"]["time"], doc["daily"]["temperature_2m_max"]) if v is not None})
    return out


def read_values(kind, texts):
    return read_ghcn_tmax(texts) if kind == "ghcn_daily" else read_open_meteo_tmax(texts)


def published_values(kind, text):
    """Values exactly as published, before any quality control: {date: TMAX and its attributes}."""
    if kind != "ghcn_daily":
        return read_open_meteo_tmax([text])
    return {parse_day(r["DATE"]): ((r.get("TMAX") or "").strip(), (r.get("TMAX_ATTRIBUTES") or "").strip())
            for r in csv.DictReader(io.StringIO(text)) if (r.get("TMAX") or "").strip()}


# ----------------------------------------------------------------------------- statistics


def q8(values, p):
    """Hyndman & Fan type-8 sample quantile; p in [0, 1]."""
    xs = sorted(values)
    n = len(xs)
    if n == 0:
        return None
    if n == 1:
        return xs[0]
    h = (n + 1.0 / 3.0) * p + 1.0 / 3.0 - 1.0  # zero-based position
    if h >= n - 1:
        return xs[-1]
    if h < 0:
        return xs[0]
    k = int(math.floor(h))
    g = h - k
    return xs[k] + (xs[k + 1] - xs[k]) * g


def days_between(a, b):
    out = []
    while a <= b:
        out.append(a)
        a += timedelta(days=1)
    return out


def yday(d):
    return (d - date(d.year, 1, 1)).days + 1


def thresholds(series, b0, b1, per, window):
    """Calendar-day percentile over a centred window, then 365 day-slots stretched onto 366."""
    dates = days_between(b0, b1)
    half = window // 2
    pool = {}
    for i, day in enumerate(dates):
        for j in range(max(0, i - half), min(len(dates), i + half + 1)):
            v = series.get(dates[j])
            if v is not None:
                pool.setdefault(yday(day), []).append(v)
    p = per / 100.0
    raw = [q8(pool.get(k, []), p) for k in range(1, 366)]
    known = [i for i, v in enumerate(raw) if v is not None]
    for a, b in zip(known, known[1:]):
        for i in range(a + 1, b):
            raw[i] = raw[a] + (raw[b] - raw[a]) * (i - a) / (b - a)
    # sample point i (0..364) sits at day 1 + i*365/364; read off days 1..366 by linear interpolation
    out = {}
    for t in range(1, 367):
        x = (t - 1) * 364.0 / 365.0
        i = min(int(math.floor(x)), 363)
        f = x - i
        lo, hi = raw[i], raw[i + 1]
        if abs(f) < 1e-12:
            out[t] = lo
        elif abs(f - 1) < 1e-12:
            out[t] = hi
        else:
            out[t] = None if lo is None or hi is None else lo + (hi - lo) * f
    return out


def fit_fill(method, station, era5, start, end):
    if method in ("none", "era5_raw"):
        return {"method": method}
    by_month = {}
    for day, s in station.items():
        if start <= day <= end and day in era5:
            by_month.setdefault(day.month, []).append((s, era5[day]))
    out = {"method": method, "months": {}}
    for m in range(1, 13):
        xy = by_month.get(m, [])
        if len(xy) < 30:
            raise ValueError(f"fill: too few pairs in month {m}")
        if method == "era5_monthly_linear":
            n = float(len(xy))
            sx = sum(e for _, e in xy)
            sy = sum(s for s, _ in xy)
            mx, my = sx / n, sy / n
            b = sum((e - mx) * (s - my) for s, e in xy) / sum((e - mx) ** 2 for _, e in xy)
            out["months"][m] = (my - b * mx, b)
        elif method == "era5_quantile_map":
            levels = [k / 100.0 for k in range(1, 100)]
            out["months"][m] = ([q8([e for _, e in xy], p) for p in levels], [q8([s for s, _ in xy], p) for p in levels])
        else:
            raise ValueError(f"unknown fill method {method}")
    return out


def apply_fill(params, day, x):
    m = params["method"]
    if m == "none" or x is None:
        return None
    if m == "era5_raw":
        return x
    p = params["months"][day.month]
    if m == "era5_monthly_linear":
        return p[0] + p[1] * x
    xs, ys = p
    if x <= xs[0]:
        return ys[0] + (x - xs[0])
    if x >= xs[-1]:
        return ys[-1] + (x - xs[-1])
    # xs[0] < x < xs[-1]: take the last k with xs[k] <= x, so xs[k] <= x < xs[k + 1]
    k = max(i for i in range(len(xs)) if xs[i] <= x)
    return ys[k] + (ys[k + 1] - ys[k]) * (x - xs[k]) / (xs[k + 1] - xs[k])


# ----------------------------------------------------------------------------- recompute a verdict


def recompute(spec, source_id, read_file, observations, through=None):
    """``observations`` maps source id -> path (in the bundle) of the observation-year file the provider fetched;
    ``through`` recomputes an interim report: the season up to that day."""
    r = spec["rule"]
    srcs = {s["id"]: s for s in spec["sources"]}
    src = srcs[source_id]

    def load(s):
        texts = [read_file(s["history"]["file"]).decode("utf-8"), read_file(observations[s["id"]]).decode("utf-8")]
        return read_values(s["kind"], texts)

    series = load(src)
    b0, b1 = parse_day(r["base_period"][0]), parse_day(r["base_period"][1])
    present = sum(1 for d in days_between(b0, b1) if d in series)
    total = (b1 - b0).days + 1
    res = {"coverage_permille": present * 1000 // total}
    if res["coverage_permille"] < r["min_base_coverage_permille"]:
        res.update(outcome=None, longest=0, reason="base_period_coverage_below_agreed_minimum", days=[], normal=None,
                   missing=0, filled=0)
        return res
    th = thresholds(series, b0, b1, r["percentile"], r["percentile_window_days"])
    year = spec["observation_year"]
    fspec = src.get("fill")
    params, other = {"method": "none"}, {}
    if fspec and fspec["method"] != "none":
        other = load(srcs[fspec["from"]])
        params = fit_fill(fspec["method"], series, other, parse_day(fspec["fit_period"][0]), parse_day(fspec["fit_period"][1]))
    s0 = date(year, int(r["season"][0][:2]), int(r["season"][0][3:]))
    s1 = date(year, int(r["season"][1][:2]), int(r["season"][1][3:]))
    res["normal"] = [milli_threshold(th[yday(day)]) for day in days_between(s0, s1)]
    if through is not None:
        s1 = min(s1, through)
    days, run, longest, missing, filled = [], 0, 0, 0, 0
    for day in days_between(s0, s1):
        v, how = series.get(day), "observed"
        if v is None:
            v = apply_fill(params, day, other.get(day))
            how = "filled" if v is not None else "missing"
        t = th[yday(day)]
        vm, tm = milli_reading(v), milli_threshold(t)
        hot = vm is not None and vm > tm
        missing += how == "missing"
        filled += how == "filled"
        run = run + 1 if hot else 0
        longest = max(longest, run)
        days.append({"date": day.isoformat(), "tx": v, "threshold": t, "v": vm, "t": tm, "status": how, "exceeds": hot})
    res.update(longest=longest, days=days, missing=missing, filled=filled)
    if missing > r["max_missing_days"]:
        res.update(outcome=None, reason="too_many_missing_days_in_season")
    elif filled > r["max_filled_days"]:
        res.update(outcome=None, reason="too_many_filled_days_in_season")
    elif through is not None and filled + (date(year, int(r["season"][1][:2]), int(r["season"][1][3:])) - s1).days > r["max_filled_days"]:
        res.update(outcome=None, reason="fill_limit_could_still_be_exceeded")
    else:
        res.update(outcome=longest >= r["min_spell_days"],
                   reason="spell_meets_minimum" if longest >= r["min_spell_days"] else "no_spell_long_enough")
    return res


# ----------------------------------------------------------------------------- chain


class Chain:
    """Minimal JSON-RPC reader for TriggerAgreement."""

    def __init__(self, rpc, contract):
        self.rpc, self.contract = rpc, contract

    def _rpc(self, method, params):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        req = urllib.request.Request(self.rpc, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as f:
            out = json.loads(f.read())
        if "error" in out:
            raise RuntimeError(out["error"])
        return out["result"]

    def call(self, sig, *words):
        data = selector(sig) + "".join(w.rjust(64, "0") for w in words)
        raw = self._rpc("eth_call", [{"to": self.contract, "data": data}, "latest"])[2:]
        return [raw[i:i + 64] for i in range(0, len(raw), 64)]

    def chain_id(self):
        return int(self._rpc("eth_chainId", []), 16)

    def agreement(self, aid):
        a = format(aid, "x")
        w = self.call("getAgreement(uint256)", a)
        addr = lambda x: "0x" + x[24:]  # noqa: E731
        n = lambda x: int(x, 16)  # noqa: E731
        p = self.call("providersOf(uint256)", a)  # dynamic array: offset, length, items
        providers = [addr(x) for x in p[2:2 + n(p[1])]]
        lw = self.call("ladderOf(uint256)", a)  # dynamic array of (uint16, uint16): offset, length, pairs
        ladder = [[n(lw[2 + 2 * i]), n(lw[3 + 2 * i])] for i in range(n(lw[1]))]
        return {"spec_hash": "0x" + w[0], "funder": addr(w[1]), "community": addr(w[2]), "checker": addr(w[3]),
                "beneficiary": addr(w[4]), "token": addr(w[5]), "amount": n(w[6]), "quorum": n(w[7]),
                "on_dispute": n(w[8]), "status": n(w[9]), "approvals": n(w[10]),
                "timing": {"window_start": n(w[12]), "window_end": n(w[13]), "report_deadline": n(w[14]),
                           "dispute_window": n(w[15])},
                "dispute_ends_at": n(w[16]), "paid_out": n(w[17]), "contested": n(w[18]), "ladder": ladder,
                "limits": {"season_days": n(w[19]), "max_missing": n(w[20]), "max_filled": n(w[21])},
                "providers": providers,
                "votes_pay": n(self.call("disputeVotesPay(uint256)", a)[0]),
                "votes_refund": n(self.call("disputeVotesRefund(uint256)", a)[0])}

    def report(self, aid, provider):
        """The provider's posted-readings record and the verdict the contract computes from it."""
        a, p = format(aid, "x"), provider[2:].lower()
        w = self.call("getRecord(uint256,address)", a, p)
        v = self.call("reportOf(uint256,address)", a, p)
        n = lambda x: int(x, 16)  # noqa: E731
        return {"verdict": n(v[0]), "longest_spell": n(v[1]), "posted": n(w[0]), "run": n(w[1]), "longest": n(w[2]),
                "filled": n(w[3]), "missing": n(w[4]), "is_final": bool(n(w[5])), "updated_at": n(w[6]), "day_log": "0x" + w[7],
                "evidence_digest": "0x" + w[8], "normal": "0x" + self.call("normalOf(uint256,address)", a, p)[0]}

    def events(self, aid):
        """Every DaysPosted event of the agreement, in chain order: when each provider posted which days."""
        topic = "0x" + keccak256(b"DaysPosted(uint256,address,uint16,uint16,uint16,uint16,uint16,bytes32,bool)").hex()
        logs = self._rpc("eth_getLogs", [{"address": self.contract, "fromBlock": "0x0", "toBlock": "latest",
                                          "topics": [topic, "0x" + format(aid, "x").rjust(64, "0")]}])
        out = []
        for lg in logs:
            w = [lg["data"][2 + 64 * i: 2 + 64 * (i + 1)] for i in range(7)]
            out.append({"provider": "0x" + lg["topics"][2][-40:], "from_day": int(w[0], 16), "count": int(w[1], 16),
                        "longest_spell": int(w[2], 16), "filled": int(w[3], 16), "missing": int(w[4], 16),
                        "evidence_digest": "0x" + w[5], "is_final": bool(int(w[6], 16))})
        return out


STATUS = {0: "None", 1: "Proposed", 2: "Locked", 3: "Disputed", 4: "Paid", 5: "Refunded", 6: "Cancelled"}
FALLBACK = {0: "refund", 1: "pay"}
VERDICT = {0: None, 1: "met", 2: "not met", 3: "abstain"}  # TriggerAgreement.Verdict
OUTCOME_OF = {"met": True, "not met": False, "abstain": None}
ALL_THREE = 7


def season_windows(year, season):
    """Contract windows implied by the season, computed independently (local time UTC+3)."""
    tz = timezone(timedelta(hours=3))
    start = int(datetime(year, int(season[0][:2]), int(season[0][3:]), tzinfo=tz).timestamp())
    end = int((datetime(year, int(season[1][:2]), int(season[1][3:]), tzinfo=tz) + timedelta(days=1)).timestamp())
    return {"window_start": start, "window_end": end, "report_deadline": end + 14 * 86400, "dispute_window": 30 * 86400}


def utc3(ts):
    return datetime.fromtimestamp(ts, timezone(timedelta(hours=3))).strftime("%Y-%m-%d %H:%M (UTC+3)")


# ----------------------------------------------------------------------------- driver


def open_bundle(path):
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
        prefix = ""
        if "bundle.json" not in names:
            prefix = next(n for n in names if n.endswith("/bundle.json"))[: -len("bundle.json")]
        return lambda name: z.read(prefix + name)
    import os
    return lambda name: open(os.path.join(path, *name.split("/")), "rb").read()


def season_part(src, values, year):
    """The values a source holds for the observation-year window the spec names."""
    a, b = parse_day(src["season_data"]["from"]), parse_day(src["season_data"]["to"])
    return {d: v for d, v in values.items() if a <= d <= b and d.year == year}


def refetch(src):
    """Download what the publisher serves now for a spec source (used with --refetch)."""
    req = urllib.request.Request(src["season_data"]["url"], headers={"User-Agent": "extremeproof-verify"})
    with urllib.request.urlopen(req, timeout=120) as f:
        return f.read()


def verify(path, rpc=None, publisher=None):
    """``publisher(source) -> bytes`` returns what the publisher serves now; None skips that comparison."""
    read = open_bundle(path)
    bundle = json.loads(read("bundle.json"))
    spec = json.loads(read("spec.json"))
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        return ok

    ch = bundle["chain"]
    aid = ch["agreement_id"]
    snap = bundle["chain_snapshot"]
    source = "snapshot in bundle"
    if rpc:
        c = Chain(rpc, ch["contract"])
        live_id = c.chain_id()
        check("chain id matches bundle", live_id == ch["chain_id"], f"live {live_id}, bundle {ch['chain_id']}")
        live = c.agreement(aid)
        reports = {p: c.report(aid, p) for p in live["providers"]}
        events = c.events(aid)
        source = f"live chain {rpc}"
        same = all(snap["agreement"].get(k) == v for k, v in live.items()) and reports == snap["reports"] and events == snap.get("events", [])
        check("bundle snapshot matches the live chain", same)
        snap = {"agreement": live, "reports": reports, "events": events}
    ag = snap["agreement"]
    chain_providers = [p.lower() for p in ag["providers"]]

    # 1. what was signed is what the contract executes
    h = "0x" + sha256_hex(canonical(spec))
    check("spec hash equals the hash approved on chain", h == ag["spec_hash"], f"spec {h} vs chain {ag['spec_hash']} ({source})")
    st = spec.get("settlement", {})
    check(f"amount: spec {st.get('amount_cents')} = chain {ag['amount']} (cents)", st.get("amount_cents") == ag["amount"])
    check(f"quorum: spec {st.get('quorum')} of {st.get('providers')} = chain {ag['quorum']} of {len(chain_providers)}",
          st.get("quorum") == ag["quorum"] and st.get("providers") == len(chain_providers))
    check(f"dispute fallback: spec '{st.get('on_dispute')}' = chain '{FALLBACK.get(ag['on_dispute'])}'",
          st.get("on_dispute") == FALLBACK.get(ag["on_dispute"]))
    ladder = st.get("payout_ladder")
    check(f"payout ladder: spec {ladder} = chain {ag.get('ladder')}, starting at the rule's {spec['rule']['min_spell_days']} days",
          ladder == ag.get("ladder") and bool(ladder) and ladder[0][0] == spec["rule"]["min_spell_days"])
    expected_windows = season_windows(spec["observation_year"], spec["rule"]["season"])
    check("contract windows equal the spec and the observation season",
          st.get("timing") == ag["timing"] == expected_windows, f"spec {st.get('timing')} chain {ag['timing']}")
    season_n = (expected_windows["window_end"] - expected_windows["window_start"]) // 86400
    limits = {"season_days": season_n, "max_missing": spec["rule"]["max_missing_days"], "max_filled": spec["rule"]["max_filled_days"]}
    check(f"data limits: {season_n} season days, at most {limits['max_missing']} missing and {limits['max_filled']} filled = chain",
          ag.get("limits") == limits, f"chain {ag.get('limits')}")
    if "parties" in st:
        check("funder, community, checker and beneficiary on chain equal the spec",
              all(st["parties"][k] == ag[k] for k in ("funder", "community", "checker", "beneficiary")))
    if "token" in st:
        check("payout token on chain equals the spec", st["token"] == ag["token"])
    if "contract" in st:
        check("contract and chain id equal the spec", st["contract"] == ch["contract"].lower() and st.get("chain_id") == ch["chain_id"])
    spec_providers = st.get("provider_addresses")
    if spec_providers:
        check("providers on chain are exactly the spec's provider per data source",
              sorted(spec_providers.values()) == sorted(chain_providers))
    source_of = {v: k for k, v in (spec_providers or {}).items()}

    # 2. what the spec pins existed before the season: history up to the end of the previous year
    year = spec["observation_year"]
    lock_by = expected_windows["window_start"]
    for s in spec["sources"]:
        hist, sd = s.get("history") or {}, s.get("season_data") or {}
        before = hist.get("through") == f"{year - 1}-12-31" and "sha256" not in sd and sd.get("from") == f"{year}-01-01"
        check(f"{s['id']}: spec pins history to {hist.get('through')} (before the lock deadline {utc3(lock_by)[:10]}) "
              f"and only names where {year} data will come from", before)
        try:
            got = sha256_hex(read(hist["file"]))
        except (KeyError, FileNotFoundError):
            check(f"pinned history present: {hist.get('file')}", False)
            continue
        check(f"pinned history hash matches spec: {hist['file']}", got == hist.get("sha256"),
              f"file {got[:16]}... spec {str(hist.get('sha256'))[:16]}...")

    # 3-5. every provider on chain, from the chain's list (not the bundle's)
    entries = {p["address"].lower(): p for p in bundle.get("providers", [])}
    verdicts = []
    spells = []  # longest spell of every provider that gave a verdict, as reported on chain
    fetched_values = {}  # source id -> [(provider label, {date: value})] for cross-provider comparison
    for addr in chain_providers:
        rep = snap["reports"][addr]
        p = entries.get(addr, {})
        sid = source_of.get(addr) or p.get("source_id")
        label = f"{sid} provider {addr[:10]}"
        if spec_providers and p.get("source_id") and p["source_id"] != sid:
            check(f"{label}: bundle labels it '{p['source_id']}' but the spec assigns '{sid}'", False)
        ev = None
        if p.get("evidence"):
            try:
                ev = json.loads(read(p["evidence"]))
            except (KeyError, FileNotFoundError):
                ev = None
        reported = VERDICT.get(rep["verdict"])
        src_spec = next((x for x in spec["sources"] if x["id"] == sid), {})
        signed_normal = src_spec.get("season_normal_mdegc")
        check(f"{label}: the daily thresholds' fingerprint on chain is the signed one",
              rep.get("normal") == normal_fingerprint(signed_normal) == (st.get("normal_keccak") or {}).get(sid),
              f"chain {str(rep.get('normal'))[:14]}…")
        if reported is None:
            check(f"{label}: no claim on chain ({rep.get('posted', 0)} days posted) — counted as absent", True)
            continue
        # Readings posted during the season: each released share rests on evidence for the days so far.
        for path in p.get("interim", []):
            try:
                iev = json.loads(read(path))
            except (KeyError, FileNotFoundError):
                check(f"{label}: interim evidence present: {path}", False)
                continue
            dig = "0x" + sha256_hex(canonical(iev))
            on_chain = [e for e in snap.get("events", []) if e["provider"] == addr and e["evidence_digest"] == dig and not e["is_final"]]
            through = parse_day(iev.get("interim_through", "1900-01-01"))
            ipaths = {oid: o["file"] for oid, o in (iev.get("observations") or {}).items()}
            ok_files = all(sha256_hex(read(o["file"])) == o["sha256"] for o in (iev.get("observations") or {}).values())
            try:
                im = recompute(spec, sid, read, ipaths, through)
            except Exception as e:  # noqa: BLE001
                check(f"{label}: interim report through {through}: recompute", False, repr(e))
                continue
            check(f"{label}: readings posted through {through}: digest on chain, data as fetched, the contract saw the "
                  f"{im['longest']}-day spell the data hold",
                  bool(on_chain) and ok_files and im["outcome"] is True and on_chain[0]["longest_spell"] == im["longest"]
                  and on_chain[0]["from_day"] + on_chain[0]["count"] == len(im["days"]),
                  f"on chain {bool(on_chain)}, files {ok_files}, recomputed {im['outcome']} / {im['longest']}")
        if not rep.get("is_final", True):
            check(f"{label}: filed no final post; the readings it posted during the season stand", True)
        verdicts.append(reported)
        if reported != "abstain":
            spells.append(rep["longest_spell"])
        if not check(f"{label}: the contract computed '{reported}' from its readings (last post {utc3(rep['updated_at'])}); its evidence is in the bundle", ev is not None):
            continue
        check(f"{label}: evidence sha256 equals the digest reported on chain", "0x" + sha256_hex(canonical(ev)) == rep["evidence_digest"])
        check(f"{label}: evidence is for this spec", ev.get("spec_hash") == h)
        obs = ev.get("observations") or {}
        paths, intact = {}, True
        for oid, o in sorted(obs.items()):
            try:
                data = read(o["file"])
            except (KeyError, FileNotFoundError):
                intact = check(f"{label}: fetched {oid} data present: {o['file']}", False) and intact
                continue
            intact = check(f"{label}: fetched {oid} data is exactly what it reported on chain (sha256 {o['sha256'][:12]}…)",
                           sha256_hex(data) == o["sha256"], f"file {sha256_hex(data)[:16]}...") and intact
            paths[oid] = o["file"]
            src = next((s for s in spec["sources"] if s["id"] == oid), None)
            if src:
                fetched_values.setdefault(oid, []).append((label, season_part(src, published_values(src["kind"], data.decode("utf-8")), year)))
        if not intact:
            continue
        try:
            mine = recompute(spec, sid, read, paths, parse_day(ev["interim_through"]) if ev.get("interim_through") else None)
        except Exception as e:  # noqa: BLE001
            check(f"{label}: recompute from pinned history + fetched data", False, repr(e))
            continue
        claimed = ev.get("outcome")
        check(f"{label}: the signed daily thresholds equal the normal recomputed from the pinned history",
              mine.get("normal") == signed_normal)
        check(f"{label}: the {rep.get('posted')} readings on chain are exactly the recomputed days "
              f"(day log, longest spell {mine['longest']}, {mine['filled']} filled, {mine['missing']} missing)",
              rep.get("posted") == len(mine["days"]) and rep.get("day_log") == day_log(mine["days"])
              and rep.get("longest") == mine["longest"] and rep.get("filled") == mine["filled"] and rep.get("missing") == mine["missing"],
              f"chain posted {rep.get('posted')} log {str(rep.get('day_log'))[:14]}…, recomputed {len(mine['days'])} {day_log(mine['days'])[:14]}…")
        if reported == "abstain":
            check(f"{label}: abstention is justified by the data ({mine['reason']})",
                  mine["outcome"] is None and mine["reason"] == ev.get("reason") and claimed is None,
                  f"recomputed {mine['outcome']} ({mine['reason']}), evidence says {ev.get('reason')}")
        else:
            check(f"{label}: recomputed verdict equals evidence ({mine['outcome']} / {claimed})", mine["outcome"] == claimed,
                  mine["reason"])
            check(f"{label}: the verdict the contract computed from the readings equals recomputation", OUTCOME_OF[reported] == mine["outcome"],
                  f"chain {reported}, recomputed {mine['outcome']}")
            check(f"{label}: longest spell on chain equals recomputation ({mine['longest']})",
                  rep["longest_spell"] == mine["longest"])
        ev_days = (ev.get("season") or {}).get("days", [])
        bad = 0
        for a, b in zip(mine["days"], ev_days):
            for k in ("tx", "threshold"):
                x, y = a[k], b[k]
                if (x is None) != (y is None) or (x is not None and abs(x - float(y)) > TOL):
                    bad += 1
            if a["status"] != b["status"] or a["exceeds"] != b["exceeds"] or a["v"] != b.get("v") or a["t"] != b.get("t"):
                bad += 1
        if mine["days"] or ev_days:
            check(f"{label}: all {len(mine['days'])} season days match (values, thresholds, gaps, exceedances)",
                  bad == 0 and len(mine["days"]) == len(ev_days), f"{bad} mismatched value{'s' if bad != 1 else ''}")
    for addr in entries:
        if addr not in chain_providers:
            check(f"bundle evidence from {addr[:10]}, who is not a provider of this agreement", False)

    # 4b. providers that fetched the same source must have got the same season values
    for oid, got in sorted(fetched_values.items()):
        if len(got) > 1:
            same = all(v == got[0][1] for _, v in got[1:])
            check(f"{' and '.join(lbl.split(' ')[0] for lbl, _ in got)} providers fetched identical {oid} season values", same)
    # 4c. optionally: do the fetched values match what the publisher serves now?
    if publisher is not None:
        label = getattr(publisher, "label", "re-downloaded from the publisher")
        for oid, got in sorted(fetched_values.items()):
            src = next(s for s in spec["sources"] if s["id"] == oid)
            try:
                today = season_part(src, published_values(src["kind"], publisher(src).decode("utf-8")), year)
            except Exception as e:  # noqa: BLE001
                check(f"{oid} season data could be fetched from {src['season_data']['publisher']} for comparison", False, repr(e))
                continue
            for lbl, vals in got:
                diff = sorted(d for d in set(vals) | set(today) if vals.get(d) != today.get(d))
                check(f"{lbl}: its {oid} season values match what {src['season_data']['publisher']} serves today ({label})",
                      not diff, f"{len(diff)} day{'s' if len(diff) != 1 else ''} differ{'' if len(diff) != 1 else 's'}, first {diff[0].isoformat()}" if diff else "")

    # 6. settlement: the share a quorum supports is paid, the share a quorum rules out is returned,
    #    only the difference is contested and resolved by unanimity or the signed fallback
    q, amount, lad = ag["quorum"], ag["amount"], ag.get("ladder") or []

    def share(spell):
        out = 0
        for days, bps in lad:
            if spell >= days:
                out = bps
        return amount * out // 10000

    s = sorted(spells)
    pay_now, owed_max = (share(s[len(s) - q]), share(s[q - 1])) if len(s) >= q else (0, amount)
    contested = owed_max - pay_now
    status = STATUS[ag["status"]]
    head = (f"settlement: spells {s} on chain, quorum {q} -> pay {pay_now} now, return {amount - owed_max} now, "
            f"contest {contested}; chain says {status}, paid {ag.get('paid_out')}")
    if status == "Locked":
        check(head + " (not settled yet)", True)
    elif contested == 0:
        check(head, status == ("Paid" if pay_now else "Refunded") and ag.get("paid_out") == pay_now)
    elif status == "Disputed":
        check(head + " (difference awaits a unanimous decision or the fallback)", ag.get("paid_out") == pay_now and ag.get("contested") == contested)
    elif status in ("Paid", "Refunded"):
        to_community = ag.get("paid_out") == pay_now + contested
        if not to_community and ag.get("paid_out") != pay_now:
            check(head + " (paid amount matches neither resolution)", False)
        else:
            bits = ag["votes_pay"] if to_community else ag["votes_refund"]
            fallback_pays = FALLBACK.get(ag["on_dispute"]) == "pay"
            how = "unanimous vote of the three parties" if bits == ALL_THREE else "signed fallback" if to_community == fallback_pays else None
            check(head + (f" via {how}" if how else " without unanimity or matching fallback"), how is not None)
    else:
        check(head, False)
    return checks


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("bundle")
    ap.add_argument("--rpc")
    ap.add_argument("--refetch", action="store_true", help="compare the season data with what each publisher serves now (network)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    checks = verify(a.bundle, a.rpc, publisher=refetch if a.refetch else None)
    if a.json:
        print(json.dumps(checks, indent=2))
    else:
        for c in checks:
            print(("PASS  " if c["ok"] else "FAIL  ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] and not c["ok"] else ""))
        n = sum(c["ok"] for c in checks)
        print(f"\n{n}/{len(checks)} checks passed")
    sys.exit(0 if all(c["ok"] for c in checks) else 1)


if __name__ == "__main__":
    main()
