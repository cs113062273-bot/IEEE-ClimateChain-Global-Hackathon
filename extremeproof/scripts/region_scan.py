"""Reproduce the regional scan (same rule at every pinned station) and audit it.

Run from the repository root:
  extremeproof/.venv/Scripts/python -m extremeproof.scripts.region_scan

Runs the SAME TypeScript module as the UI (web/lib/region.ts) on the pinned
tables, then re-evaluates every 2021-2025 source verdict from the raw files with
the Python engine through the signed-spec path the providers use. Years inside
the base period are bootstrapped in the tables and cannot be settled by a spec,
so the 1966-2025 counts are reported, not re-audited here.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from extremeproof.climate.specs import SITES, make_spec
from extremeproof.climate.trigger import evaluate
from extremeproof.scripts.compare_relief import RULE

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("rule", "comparison", "region", "sites")


def browser_scan(sites):
    payload = {s: json.loads((ROOT / "web/public/data" / f"{s}.json").read_text(encoding="utf-8")) for s in sites}
    with tempfile.TemporaryDirectory(prefix="ep-region-audit-") as td:
        temp = Path(td)
        for name in MODULES:
            text = (ROOT / "web/lib" / f"{name}.ts").read_text(encoding="utf-8")
            for dep in MODULES:  # Node needs explicit .ts suffixes; nothing else changes
                text = text.replace(f'from "./{dep}"', f'from "./{dep}.ts"')
            (temp / f"{name}.ts").write_text(text, encoding="utf-8")
        js = """
          import fs from 'node:fs';
          const {regionScan} = await import(process.argv[1]);
          const {SITES} = await import(process.argv[2]);
          const {data, rule} = JSON.parse(fs.readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify({sites: SITES, scan: regionScan(SITES, data, rule)}));
        """
        run = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", js,
                              (temp / "region.ts").as_uri(), (temp / "sites.ts").as_uri()],
                             input=json.dumps({"data": payload, "rule": RULE}), text=True,
                             capture_output=True, check=True, encoding="utf-8")
        return json.loads(run.stdout)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # station names on a Windows console
    out = browser_scan(list(SITES))
    ui_sites = {s["id"]: s["station"] for s in out["sites"]}
    assert ui_sites == {k: v["station"] for k, v in SITES.items()}, "web/lib/sites.ts and climate/specs.py list different stations"
    checks = 0
    for row in out["scan"]["rows"]:
        for season in row["recent"]:
            spec = make_spec(site=row["id"], year=season["year"], base=(1991, 2020), percentile=RULE["percentile"],
                             min_spell_days=RULE["minSpell"], max_missing_days=RULE["maxMissing"],
                             max_filled_days=RULE["maxFilled"], on_dispute=RULE["onDispute"])
            for key, source in (("a", "station"), ("b", "era5")):
                ev = evaluate(spec, source)
                state = "nodata" if ev["outcome"] is None else "met" if ev["outcome"] else "not"
                assert season[key]["state"] == state, (row["id"], season["year"], source, season[key], ev.get("reason"))
                if ev["outcome"] is not None:
                    assert season[key]["longest"] == ev["season"]["longest_spell"], (row["id"], season["year"], source)
                if row["noNormal"] and source == "station":
                    assert ev["reason"] == "base_period_coverage_below_agreed_minimum", (row["id"], ev["reason"])
                checks += 1
    s = out["scan"]
    result = {
        "schema": "extremeproof.region-scan.v1", "rule": RULE,
        "summary": {k: s[k] for k in ("usable", "noNormal", "decidable", "contested", "placesWithConflict", "recentOpen")},
        "rows": [{k: r[k] for k in ("id", "name", "station", "baseCoverage", "noNormal", "history")}
                 | {"recent": {x["year"]: x["policies"]["dual"]["outcome"] + ("" if x["policies"]["dual"]["outcome"] != "dispute" else f" ({x['policies']['dual']['reason']})")
                               for x in r["recent"]}} for r in s["rows"]],
        "audited_source_verdicts_2021_2025": checks,
        "input_sha256": {k: hashlib.sha256((ROOT / "web/public/data" / f"{k}.json").read_bytes()).hexdigest() for k in SITES},
        "scope": "Exploratory scan over summers already seen; shows where the choice of record changes the decision, not which record is right. "
                 "1966-2025 counts include bootstrapped base-period years from the precomputed tables.",
    }
    dest = ROOT / "experiments" / "region_scan.json"
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: {checks} source verdicts 2021-2025 agree with raw-data evaluation; wrote {dest}")
    print(json.dumps(result["summary"], ensure_ascii=False))
    for r in result["rows"]:
        print(f"{r['name']:<11} {r['station']} base {r['baseCoverage'] / 10:5.1f}%  disagree {r['history']['contested']:>2}  thin {r['history']['thin']:>2}  {r['recent']}")


if __name__ == "__main__":
    main()
