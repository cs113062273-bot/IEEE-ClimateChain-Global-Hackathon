"""Reproduce the design comparison; audit browser verdicts against pinned raw data.

Run from the repository root:
  extremeproof/.venv/Scripts/python -m extremeproof.scripts.compare_relief

Uses Node 24's built-in TypeScript support to run the SAME comparison module as
the UI. Independently evaluates its source verdicts with the Python engine.
No services, wallets, API keys, downloads or chain writes are needed.
"""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from extremeproof.climate.specs import make_spec
from extremeproof.climate.trigger import DISPUTE_DAYS, REPORT_DAYS, evaluate

ROOT = Path(__file__).resolve().parents[1]
RULE = dict(variant="station_qm", base="1991-2020", percentile=90, minSpell=6,
            maxMissing=0, maxFilled=122, onDispute="refund")
CASES = {
    "default": RULE,
    "limited_fill_refund": {**RULE, "maxFilled": 60},
    "limited_fill_pay": {**RULE, "maxFilled": 60, "onDispute": "pay"},
    "ten_day_trigger": {**RULE, "minSpell": 10},
}


def browser_results():
    payload = {site: json.loads((ROOT / "web/public/data" / f"{site}.json").read_text(encoding="utf-8"))
               for site in ("antalya", "mugla")}
    # Only the import suffix changes; calculations are the exact UI module.
    with tempfile.TemporaryDirectory(prefix="ep-comparison-audit-") as td:
        temp = Path(td)
        for name in ("rule", "comparison"):
            text = (ROOT / "web/lib" / f"{name}.ts").read_text(encoding="utf-8")
            (temp / f"{name}.ts").write_text(text.replace('from "./rule"', 'from "./rule.ts"'), encoding="utf-8")
        js = """
          import fs from 'node:fs';
          const {compareHistory, COMPARISON_ASSUMPTIONS} = await import(process.argv[1]);
          const {data, cases} = JSON.parse(fs.readFileSync(0, 'utf8'));
          const results = Object.fromEntries(Object.entries(data).map(([site, d]) => [site,
            Object.fromEntries(Object.entries(cases).map(([name, rule]) => [name, compareHistory(d, rule)]))]));
          process.stdout.write(JSON.stringify({results, assumptions: COMPARISON_ASSUMPTIONS}));
        """
        run = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", js,
                              (temp / "comparison.ts").as_uri()],
                             input=json.dumps({"data": payload, "cases": CASES}), text=True,
                             capture_output=True, check=True, encoding="utf-8")
        return json.loads(run.stdout)


def main():
    output = browser_results()
    assumptions = output["assumptions"]
    assert [assumptions[k] for k in ("reportDays", "disputeDays")] == [REPORT_DAYS, DISPUTE_DAYS]
    checks = 0
    for site, cases in output["results"].items():
        for name, history in cases.items():
            rule = CASES[name]
            for row in history["seasons"]:
                spec = make_spec(site=site, year=row["year"], base=(1991, 2020), percentile=rule["percentile"],
                                 min_spell_days=rule["minSpell"], max_missing_days=rule["maxMissing"],
                                 max_filled_days=rule["maxFilled"], on_dispute=rule["onDispute"])
                evs = [evaluate(spec, source) for source in ("station", "era5")]
                for key, ev in zip(("a", "b"), evs):
                    state = "nodata" if ev["outcome"] is None else "met" if ev["outcome"] else "not"
                    assert row[key]["state"] == state, (site, name, row["year"], key)
                    if ev["outcome"] is not None:
                        assert row[key]["longest"] == ev["season"]["longest_spell"]
                    checks += 1
                a, b = (e["outcome"] for e in evs)
                expected = {"station": a, "era5": b, "dual": a if a is not None and a == b else None}
                for policy, flag in expected.items():
                    r = row["policies"][policy]
                    outcome = "dispute" if flag is None else "pay" if flag else "refund"
                    assert r["outcome"] == outcome
                    final = rule["onDispute"] if flag is None else outcome
                    assert r["final"] == final
                    assert r["payoutCents"] == (spec["settlement"]["amount_cents"] if final == "pay" else 0)
                    days = DISPUTE_DAYS if outcome == "dispute" else 0  # an abstention is a report: no deadline wait
                    assert r["modelledDays"] == days
                    checks += 1
    output.update({
        "schema": "extremeproof.comparison-audit.v1", "cases": CASES,
        "audited_source_and_policy_rows": checks,
        "input_sha256": {s: hashlib.sha256((ROOT / "web/public/data" / f"{s}.json").read_bytes()).hexdigest()
                         for s in output["results"]},
        "scope": "Post-review exploratory design comparison. No new method selection, independent holdout, observed payment times, household losses or real aid outcomes.",
    })
    dest = ROOT / "experiments" / "decision_comparison.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: {checks} source/policy rows agree with raw-data evaluation; wrote {dest}")
    for site, cases in output["results"].items():
        for name, history in cases.items():
            print(site, name, json.dumps(history["summaries"], sort_keys=True))


if __name__ == "__main__":
    main()
