"""How much of the payout an in-season release gets to people before the season ends.

Run from the repository root:
  extremeproof/.venv/Scripts/python -m extremeproof.scripts.inseason

For every station and summer 2021-2025 under the default graded rule (90th percentile of
1991-2020, 6+ days, quantile-mapped station gaps), replays the weekly in-season check the
providers run: each Sunday, each provider evaluates the season published so far (5 days
behind) and the share both support is released. Uses the same engine and the same interim
rule (a spell already seen; fill limit cannot still be exceeded) as the providers.
Writes experiments/inseason_release.json.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from extremeproof.climate.specs import SITES, make_spec
from extremeproof.climate.trigger import PUBLICATION_LAG_DAYS, evaluate, share_bps

ROOT = Path(__file__).resolve().parents[1]
YEARS = range(2021, 2026)  # summers after the 1991-2020 base period can be settled by a spec


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = []
    for site in SITES:
        for year in YEARS:
            spec = make_spec(site=site, year=year, base=(1991, 2020), payout="graded")
            ladder = spec["settlement"]["payout_ladder"]
            final = [evaluate(spec, s) for s in ("station", "era5")]
            if any(e["outcome"] is None for e in final):
                rows.append({"site": site, "year": year, "final_share_bps": None, "note": "a provider has too little data"})
                continue
            final_bps = min(share_bps(ladder, e["season"]["longest_spell"]) for e in final)
            released, first = 0, None
            check = date(year, 6, 1) + timedelta(days=7)
            while check < date(year, 10, 1):
                through = check - timedelta(days=PUBLICATION_LAG_DAYS)
                spells = []
                for s in ("station", "era5"):
                    e = evaluate(spec, s, through=through)
                    spells.append(e["season"]["longest_spell"] if e["outcome"] is True else 0)
                now = min(share_bps(ladder, x) for x in spells)
                if now > released:
                    released = now
                    first = first or check.isoformat()
                check += timedelta(days=7)
            rows.append({"site": site, "year": year, "final_share_bps": final_bps, "released_in_season_bps": released,
                         "first_release": first})
    paid = [r for r in rows if r.get("final_share_bps")]
    total = sum(r["final_share_bps"] for r in paid)
    early = sum(min(r["released_in_season_bps"], r["final_share_bps"]) for r in paid)
    out = {
        "schema": "extremeproof.inseason.v1", "years": [YEARS.start, YEARS.stop - 1], "rule": "graded, p90 of 1991-2020, 6+ days, quantile-mapped gaps",
        "publication_lag_days": PUBLICATION_LAG_DAYS, "check_every_days": 7,
        "summers_with_payment_agreed_by_both": len(paid), "share_of_agreed_payout_released_before_october": round(early / total, 3) if total else None,
        "first_release_months": {m: sum(1 for r in paid if (r.get("first_release") or "")[5:7] == m) for m in ("06", "07", "08", "09")},
        "rows": rows,
        "scope": "Retrospective replay on pinned final data with an assumed 5-day publication lag; data revisions are not modelled.",
    }
    dest = ROOT / "experiments" / "inseason_release.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{len(paid)} summers where both records support a payment; "
          f"{out['share_of_agreed_payout_released_before_october']:.0%} of that payout released before 1 October; "
          f"first release by month {out['first_release_months']}; wrote {dest}")


if __name__ == "__main__":
    main()
