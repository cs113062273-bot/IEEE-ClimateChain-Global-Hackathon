"""Reproduce the rule finder (choose a rule by its purpose) and audit its counts.

Run from the repository root:
  extremeproof/.venv/Scripts/python -m extremeproof.scripts.rule_finder

Runs the SAME TypeScript module as the UI (web/lib/finder.ts) for each target
return period and each dispute fallback (the target counts final payments, so a
"pay" fallback changes which rules meet it), then re-evaluates every candidate's
agreement outcome and final payment from the raw
files with the Python engine, for every summer the signed-spec path can settle
(years after the candidate's base period). Years inside a base period are
bootstrapped in the precomputed tables and are reported, not re-audited.

The one-day stability check (payments that hinge on one day) is audited the same
way: the module's per-summer outcomes with the spell rule one day shorter and
longer must reproduce its hinge counts, and every one of those outcomes outside
the base period is re-evaluated from the raw files.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from extremeproof.climate.specs import make_spec
from extremeproof.climate.trigger import evaluate
from extremeproof.scripts.compare_relief import RULE

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("rule", "comparison", "finder")
SITES = ("antalya", "mugla")
TARGETS = (3, 5, 10)
FALLBACKS = ("refund", "pay")


def browser_finder():
    payload = {s: json.loads((ROOT / "web/public/data" / f"{s}.json").read_text(encoding="utf-8")) for s in SITES}
    with tempfile.TemporaryDirectory(prefix="ep-finder-audit-") as td:
        temp = Path(td)
        for name in MODULES:
            text = (ROOT / "web/lib" / f"{name}.ts").read_text(encoding="utf-8")
            for dep in MODULES:  # Node needs explicit .ts suffixes; nothing else changes
                text = text.replace(f'from "./{dep}"', f'from "./{dep}.ts"')
            (temp / f"{name}.ts").write_text(text, encoding="utf-8")
        js = """
          import fs from 'node:fs';
          const F = await import(process.argv[1]);
          const {compareSeason} = await import(process.argv[2]);
          const {data, rule, targets, fallbacks} = JSON.parse(fs.readFileSync(0, 'utf8'));
          const out = {};
          for (const [site, d] of Object.entries(data)) {
            out[site] = {};
            for (const fb of fallbacks) for (const t of targets) {
              const r = F.findRules(d, {...rule, onDispute: fb}, t);
              const cands = [r.current, ...r.picks];
              out[site][`${fb}/1-in-${t}`] = { excluded: r.excluded, candidates: cands.map((c) => ({
                rule: c.rule, now: c.now, then: c.then, last10: c.last10, returnPeriod: c.returnPeriod,
                agreementReturnPeriod: c.agreementReturnPeriod, hinge: c.hinge,
                neighbours: Object.fromEntries([c.rule.minSpell - 1, c.rule.minSpell + 1].map((m) => [m,
                  Object.fromEntries(Array.from({length: 30}, (_, i) => 1996 + i)
                    .map((y) => { const p = compareSeason(d, {...c.rule, minSpell: m}, y).policies.dual; return [y, [p.outcome, p.final]]; }))])),
                outcomes: Object.fromEntries(Array.from({length: 60}, (_, i) => 1966 + i)
                  .map((y) => { const p = compareSeason(d, c.rule, y).policies.dual; return [y, [p.outcome, p.final]]; })) })) };
            }
          }
          process.stdout.write(JSON.stringify(out));
        """
        run = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", js,
                              (temp / "finder.ts").as_uri(), (temp / "comparison.ts").as_uri()],
                             input=json.dumps({"data": payload, "rule": RULE, "targets": TARGETS, "fallbacks": FALLBACKS}), text=True,
                             capture_output=True, check=True, encoding="utf-8")
        return json.loads(run.stdout)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out = browser_finder()
    cache, checks, hinge_checks = {}, 0, 0

    def dual(site, r, min_spell, y):
        b0, b1 = (int(x) for x in r["base"].split("-"))
        key = (site, r["base"], r["percentile"], min_spell, y)
        if key not in cache:
            spec = make_spec(site=site, year=y, base=(b0, b1), percentile=r["percentile"],
                             min_spell_days=min_spell, max_missing_days=r["maxMissing"],
                             max_filled_days=r["maxFilled"], on_dispute=r["onDispute"])
            a, b = (evaluate(spec, s)["outcome"] for s in ("station", "era5"))
            cache[key] = "dispute" if a is None or b is None or a != b else "pay" if a else "refund"
        return cache[key]

    for site, by_target in out.items():
        for target, res in by_target.items():
            for c in res["candidates"]:
                r = c["rule"]
                b0, b1 = (int(x) for x in r["base"].split("-"))
                for y, (outcome, final) in c["outcomes"].items():
                    y = int(y)
                    if y <= b1:
                        continue  # inside the base period: bootstrapped, cannot be settled by a spec
                    got = dual(site, r, r["minSpell"], y)
                    assert got == outcome, (site, target, r, y, got, outcome)
                    expected_final = "pay" if outcome == "pay" or (outcome == "dispute" and r["onDispute"] == "pay") else "refund"
                    assert final == expected_final, (site, target, r, y, final)
                    checks += 1
                # One-day stability: the hinge counts follow from the neighbouring rules' outcomes,
                # and each of those outcomes agrees with the raw-data evaluation.
                m, shorter, longer = r["minSpell"], c["neighbours"][str(r["minSpell"] - 1)], c["neighbours"][str(r["minSpell"] + 1)]
                spare = short = 0
                for y in range(1996, 2026):
                    paid = c["outcomes"][str(y)][1] == "pay"
                    spare += paid and longer[str(y)][1] != "pay"
                    short += (not paid) and m > 1 and shorter[str(y)][1] == "pay"
                    for spell, row in ((m - 1, shorter), (m + 1, longer)):
                        if y > b1 and spell >= 1:
                            got = dual(site, r, spell, y)
                            assert got == row[str(y)][0], (site, target, r, spell, y, got, row[str(y)])
                            hinge_checks += 1
                assert c["hinge"] == {"noDayToSpare": spare, "oneDayShort": short}, (site, target, r, c["hinge"], spare, short)
                # The headline count: final payments = agreement pays + disputes the fallback pays.
                n = c["now"]
                assert n["finalPays"] == n["pays"] + (n["contested"] + n["thin"] if r["onDispute"] == "pay" else 0), (site, target, r)
    dest = ROOT / "experiments" / "rule_finder.json"
    result = {
        "schema": "extremeproof.rule-finder.v2", "base_rule": RULE, "targets": TARGETS, "fallbacks": FALLBACKS,
        "target_means": "final payments to the community under the signed fallback (agreement pays + disputes the fallback pays)",
        "audited_candidate_summers": checks, "audited_one_day_neighbour_summers": hinge_checks,
        "independent_evaluations": len(cache),
        "results": {s: {t: {"excluded": v["excluded"], "candidates": [{k: c[k] for k in ("rule", "returnPeriod", "agreementReturnPeriod", "hinge", "now", "then", "last10")}
                                                                       for c in v["candidates"]]}
                        for t, v in bt.items()} for s, bt in out.items()},
        "scope": "Exploratory, over summers already seen. Shows how often each complete rule would have paid, disputed or waited; not which rule is right.",
    }
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PASS: {checks} candidate-summer outcomes and {hinge_checks} one-day-neighbour outcomes agree with raw-data "
          f"evaluation ({len(cache)} evaluations); hinge counts reproduced; wrote {dest}")
    for site, bt in result["results"].items():
        for t, v in bt.items():
            row = " | ".join(f"{c['rule']['base']} p{c['rule']['percentile']} {c['rule']['minSpell']}d: "
                             f"paid {c['now']['finalPays']}/30 ({c['now']['pays']} by agreement), {c['now']['contested'] + c['now']['thin']} disp, "
                             f"hinge {c['hinge']['noDayToSpare']}+{c['hinge']['oneDayShort']}"
                             for c in v["candidates"])
            print(f"{site} {t}: {row}")


if __name__ == "__main__":
    main()
