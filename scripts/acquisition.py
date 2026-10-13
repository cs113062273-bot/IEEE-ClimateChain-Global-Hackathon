"""Small, cached, attributable source acquisition helpers; Python 3.11+."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw"
PROCESSED = ROOT / "data/processed"
MANIFEST = ROOT / "data/manifests"
USER_AGENT = "GridProof/0.1 educational noncommercial hackathon research"
UTC = timezone.utc


def now_utc():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_text(value):
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value, allow_naive=False):
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None:
        if not allow_naive:
            raise ValueError(f"Timezone missing: {value}")
        d = d.replace(tzinfo=UTC)
    return d.astimezone(UTC)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def fetch(url, path, *, refresh=False, attempts=3, timeout=45):
    """Cache successful raw response and original HTTP metadata; never fake a success."""
    path = Path(path)
    sidecar = path.with_suffix(path.suffix + ".http.json")
    if path.exists() and sidecar.exists() and not refresh:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if meta["url"] != url:
            refresh = True
        elif meta["sha256"] != sha256(path):
            raise ValueError(f"Cached snapshot hash mismatch: {path}")
        else:
            return path.read_bytes(), meta
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/html,text/csv,*/*"}
    if refresh and sidecar.exists():
        old = json.loads(sidecar.read_text(encoding="utf-8"))
        if old.get("etag") and old.get("url") == url:
            headers["If-None-Match"] = old["etag"]
    failures = []
    for attempt in range(attempts):
        retrieved = now_utc()
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read()
                meta = {"url": url, "final_url": response.url, "fetched_utc": retrieved,
                        "http_status": response.status, "content_type": response.headers.get("Content-Type"),
                        "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified"),
                        "http_date": response.headers.get("Date"), "byte_size": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(), "path": relative(path)}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            write_json(sidecar, meta)
            print(f"FETCH {meta['http_status']} {len(body)} bytes {relative(path)}", flush=True)
            time.sleep(0.25)
            return body, meta
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and path.exists():
                old["last_checked_utc"] = retrieved
                write_json(sidecar, old)
                return path.read_bytes(), old
            failures.append({"fetched_utc": retrieved, "url": url, "http_status": exc.code,
                             "error": str(exc), "response_body": exc.read(2048).decode("utf-8", errors="replace")})
            if exc.code not in (408, 429, 500, 502, 503, 504, 529):
                break
            delay = min(10, int(exc.headers.get("Retry-After", "0")) if exc.headers.get("Retry-After", "0").isdigit() else 0)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            failures.append({"fetched_utc": retrieved, "url": url, "http_status": None,
                             "error": f"{type(exc).__name__}: {exc}"})
            delay = 0
        if attempt < attempts - 1:
            time.sleep(max(delay, 2 ** attempt))
    write_json(path.with_suffix(path.suffix + ".error.json"), {"attempts": failures})
    last = failures[-1]
    raise RuntimeError(f"{last['error']} (HTTP {last.get('http_status')}) from {url}; response {last.get('response_body','')[:180]}")


def record(source_id, **kwargs):
    entry = {"source_id": source_id, "checked_utc": now_utc(), **kwargs}
    write_json(MANIFEST / "artifacts" / f"{source_id}.json", entry)
    return entry


def numeric(value):
    if value is None or str(value).strip().lower() in ("", "null", "nan", "none", "na"):
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def write_csv(path, rows):
    if not rows:
        raise ValueError("No records; refusing to create a misleading empty dataset")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def profile(rows, granularity_minutes=30):
    starts = [parse_utc(r["start_utc"]) for r in rows]
    ends = [parse_utc(r["end_utc"]) for r in rows]
    duplicate_count = len(starts) - len(set(starts))
    invalid_duration = sum((b-a).total_seconds() != granularity_minutes*60 for a,b in zip(starts, ends))
    gaps = [{"previous": utc_text(a), "next": utc_text(b), "minutes": (b-a).total_seconds()/60}
            for a,b in zip(starts, starts[1:]) if b-a != timedelta(minutes=granularity_minutes)]
    missing = {key: sum(r.get(key) in (None, "") for r in rows) for key in rows[0]} if rows else {}
    types = {}
    ranges = {}
    for key in rows[0] if rows else []:
        values=[r[key] for r in rows if r.get(key) not in (None, "")]
        try:
            numbers=[float(x) for x in values]
            types[key]="number_or_null" if missing[key] else "number"
            ranges[key]={"min":min(numbers),"max":max(numbers)} if numbers else None
        except (ValueError,TypeError):
            types[key]="string_or_null" if missing[key] else "string"
    return {"row_count": len(rows), "coverage_start_utc": utc_text(min(starts)) if starts else None,
            "coverage_end_utc_exclusive": utc_text(max(ends)) if ends else None,
            "granularity_minutes": granularity_minutes, "timezone": "UTC", "columns": list(rows[0]) if rows else [],
            "missing_count": missing, "missing_rate": {k:v/len(rows) for k,v in missing.items()},
            "column_types": types, "numeric_ranges":ranges,
            "duplicate_timestamps": duplicate_count, "invalid_interval_duration": invalid_duration,
            "out_of_order": starts != sorted(starts), "gap_count": len(gaps), "gaps": gaps[:20]}


def settlement_interval(settlement_date, period):
    """Elexon GB settlement day starts London midnight; periods advance in UTC."""
    local_date = date.fromisoformat(settlement_date)
    zone = ZoneInfo("Europe/London")
    start = datetime.combine(local_date, datetime.min.time(), zone).astimezone(UTC)
    following = datetime.combine(local_date+timedelta(days=1), datetime.min.time(), zone).astimezone(UTC)
    slots = int((following-start).total_seconds()/1800)
    period = int(period)
    if not 1 <= period <= slots:
        raise ValueError(f"Settlement period {period} invalid for {local_date} ({slots} periods)")
    a = start + timedelta(minutes=30*(period-1))
    return a, a+timedelta(minutes=30), slots
