# Decision review: from climate calculations to a funding choice

Implemented 2026-10-20, after external competitor review. This adds a decision
workflow to the existing product; it does not introduce a new climate model,
change the contracts or claim new real-world climate impact.

## User and task

A local heatwave relief fund's agreement designer must agree with the community
representative and checker on a seasonal payment rule. Before locking the money,
they need to know how source choices and data limits change payments, disputes
and waiting. The prototype settles after summer, not before a disaster. The
specific relief expenditure and an adopting organisation remain unvalidated.

## What changed

- The home page starts with comparing relief decisions, before the statistical
  explanation. Muğla 2021 is the default inspection: station says no, ERA5 yes.
- The designer compares station-only, ERA5-only and the actual two-source
  agreement for the same five summers, threshold, gap rule, quality limits,
  50,000 DEMO deposit and unresolved-dispute fallback. Single-source policies
  are counterfactuals, not additional deployable contract modes.
- Selecting a summer reveals both spell lengths, missing/filled days, the
  payment consequence and modelled wait. The review button writes that exact
  site's/year's/current rule into the existing signing flow.
- The signing summary derives the consequences from the agreement text,
  including its amount and fallback. Later edits to the designer do not change
  the proposed or locked agreement.
- Downloadable JSON records inputs, SHA-256 of the web input table, settings,
  per-season outcomes, totals and assumptions. This is an unsigned design
  report. The existing signed agreement verification bundle remains the way
  to verify raw sources, provider evidence and actual settlement.
- All 61 summers and alternative gap methods remain available under details.

## Fair comparison and limitations

2021–2025 follows both selectable reference periods. These years have already
been inspected: this is a retrospective, exploratory design comparison, not a
new holdout, method-selection experiment or prospective simulation. It uses
pinned final weather records; data publication times are not reconstructed.

Every policy receives the same source verdicts and quality limits. Station-only
uses the same station gap rule as provider A; ERA5-only uses provider B. The
two-source policy requires agreement. No verdict is not silently counted as no.
All unresolved cases follow the chosen fallback, without unanimous resolution.
Five seasons are five separate agreements, not an annual budget or forecast.

Waiting is modelled in whole days after the season ends: promptly usable reports
permit direct settlement; disagreement adds 30 days; missing reports exhaust
the approximately 14-day reporting window, then add 30 days. Contract strict
deadline comparisons require an additional second/block. Publication lag,
transaction latency and operator availability are excluded. These are not
observed waiting times or guaranteed upper bounds. An earlier unanimous vote
can resolve a dispute; an absent operator can make it last longer.

There is no loss, health, vulnerability or actual aid-delivery ground truth.
Neither higher payouts nor more disputes is evidence of better relief. Provider
A's ERA5-based filling also means A and B are not independent observations.

## Reproduced results

Each season's deposit is 50,000 DEMO. Totals below assume no unanimous resolution
and prompt execution of the fallback. They describe fund allocation, not value
saved or damage avoided.

| Site / rule | Station-only payouts | ERA5-only payouts | Two-source payouts | Two-source disputes |
|---|---:|---:|---:|---:|
| Antalya, default 6 days, fill limit 122, refund fallback | 200,000 | 200,000 | 200,000 | 0 |
| Muğla, same default | 150,000 | 200,000 | 150,000 | 1, ~30 days |
| Antalya, fill limit 60, refund fallback | 50,000 | 200,000 | 50,000 | 3, ~44 days each |
| Antalya, fill limit 60, pay fallback | 200,000 | 200,000 | 200,000 | 3, ~44 days each |
| Antalya, 10-day threshold, refund fallback | 50,000 | 150,000 | 50,000 | 2, ~30 days each |
| Muğla, 10-day threshold, refund fallback | 50,000 | 200,000 | 50,000 | 3, ~30 days each |

Important negative result: the default Antalya policy changes nothing compared
with a single source. The default Muğla policy delays one case and, with a refund
fallback, pays less than ERA5 alone. The contribution demonstrated here is making
that choice inspectable before signing; it is not proof that two sources improve
relief outcomes.

Reproduce from the repository root (Python environment and Node 24 installed):

```powershell
extremeproof\.venv\Scripts\python -m extremeproof.scripts.compare_relief
```

This executes the actual browser comparison module under Node and independently
evaluates its provider verdicts from pinned raw data using the Python engine.
It checks 200 source/policy rows across two locations, four rule settings and
five summers, including payout amounts and waiting assumptions. Output:
[`experiments/decision_comparison.json`](../experiments/decision_comparison.json).

The four settings are declared examples and sensitivities, chosen after previous
review. No winning setting was selected, and existing model results are retained.

## Validation of this change

- Production build and TypeScript checks passed.
- Browser suite: 13 passed; two duplicate mobile-only draft-state checks are
  intentionally skipped. It exercises the comparison, exported input hash,
  fallback changes, strict data limits, signed-text isolation, all three original
  cases, settlement, tampering and independent verification at 1440/390/320 px.
- The new compare → export → sign → settle → verify case was rerun successfully
  against the production build at port 3000.
- Production screenshots were inspected at desktop and mobile, including dark
  mode. At 1440/390/320 px in both themes: no page-level horizontal overflow or
  browser page errors. The comparison table has its own labelled horizontal
  scrolling area on small screens.
- Climate engine, verifier and contracts were not modified. The prior 94 Python
  and 22 contract test results are retained, not represented as rerun this round.
- The demo stack was restarted on the production build and the chain reset
  after testing. No public deployment, submission, commit or index edit.

## External benchmark driving this change

- [Official track and mission](https://ieee-climatechain-hack.devpost.com/):
  accessible, reliable climate data; environmental accountability and action.
- [Official judging criteria](https://ieee-climatechain-hack.devpost.com/rules):
  climate relevance, innovation, implementation, usefulness and communication;
  no published weights.
- [Etherisc](https://www.etherisc.com/about/) and
  [Arbol](https://www.arbol.io/help/agents-brokers/the-basics) already describe
  climate-data-based payout products. Automatic weather payouts are not novel.
- [RainGuard](https://ethglobal.com/showcase/rainguard-vgfqo) won a Chainlink
  award at ETHGlobal Cannes. Its public main-branch settlement contract inspected
  on 2026-10-20 still calls a mock weather decision; the showcase is not proof
  that every advertised integration runs.
- Same-event [PLUME](https://devpost.com/software/plume-earth-s-first-climate-bug-bounty-network)
  and [CanopyProof](https://devpost.com/software/canopyproof-lwsvz4) also connect
  climate evidence and enforceable funding/asset decisions. Public recomputation
  alone is not a unique advantage. Their performance claims were not rerun.

The official gallery was unpublished on 2026-10-20. These public individual
entries are a partial comparison, not a ranking or evidence of likely placing.

## Refinement 2026-10-21: decision brief and payment purpose

Checked by using the production page at 1440/390/320 px; no real users were
interviewed. Three things blocked a five-minute decision in the previous version:
the open question was buried in a repeated table, the two-source column was the
last one and scrolled off a phone, and nothing said what the season-end payment
would pay for.

- A decision brief now opens the comparison. It sorts the 2021–2025 summers into
  "records agree" (settle themselves), "records disagree" and "too little data"
  (names the abstaining provider), then asks the one choice that is open: where
  the money goes if the parties cannot agree. The answer shows the money and the
  modelled wait for exactly those summers. It sets the same fallback as the
  design control, so compare, export and sign still read one rule.
- The brief also counts disagreements and thin-data summers over the full record
  under the current rule (Muğla default: 8 and 1 of 60 summers 1966–2025;
  Antalya with fill limit 60: 7 and 12). It states that two records do not make
  a payment more correct; they move an arbitrary source choice into a decision
  made before signing, at the cost of about 30 days (44 when a provider abstains).
- The two-source column is now first in the table.
- "What is the payment for?" describes an example design without a partner: a
  season-end payment into a farmers' cooperative's hardship fund. It contrasts
  this with event-driven wage cover such as SEWA's extreme-heat product in India
  ([NPR](https://www.npr.org/sections/goats-and-soda/2025/07/16/g-s1-76948/hot-temperatures-insurance-gig-workers-india),
  [PreventionWeb](https://www.preventionweb.net/news/how-heatwaves-have-sparked-new-ways-women-farmers-india-protect-their-crops)),
  whose 2023 pilot threshold had to be lowered, and notes that India's RWBCIS
  lists high temperature as a crop weather peril
  ([policy wording](https://www.iffcotokio.co.in/content/dam/iffcotokio/policy-wordings/other-insurance/RWBCIS_Policy_Wording.pdf)).
  A search found no heat-index product among TARSİM's listed perils in Türkiye;
  that is a search result, not proof that none exists.

Validation: typecheck and production build passed; `compare_relief` exit 0;
browser suite 13 passed, 2 intentionally skipped, with the strict-data test
extended to check the brief headline, abstaining provider and that the brief's
choice sets the same fallback (150,000 DEMO under pay). No contract, engine or
verifier change.


## Scope correction 2026-10-21

After rereading the official overview and rules, the user explicitly cancelled
mobile-specific work. The new mobile policy selector and its layout overrides
have been removed. Existing shared functionality and Claude's decision brief
are retained. The desktop inspect shortcut and draft explanation remain.

The competition asks for track alignment, a working prototype, public source,
a focused 3?5 minute demo, and an explanation of the problem, users and adoption.
Its five criteria cover climate impact, innovation, execution, practical use
and presentation. Mobile support is not a stated requirement. Do not treat it
as an acceptance gate or spend further time on phone layouts or phone tests.
Priorities are the climate problem, demonstrable user benefit, meaningful use
of blockchain and a clear desktop demonstration.

Sources checked on 2026-10-21:
- https://ieee-climatechain-hack.devpost.com/
- https://ieee-climatechain-hack.devpost.com/rules

### UI copy cleanup (2026-10-21)

Each limitation now appears once in the page instead of up to six times: need
is not measured (step 1 intro), A and B are not independent (signed rule and
footer), timing is modelled ("How to read this comparison"). Internal notes
were removed from the page: that the summary reads the signed text, that
2021–2025 had already been inspected and is not an independent test, that data
are pinned final values without publication times, the bootstrapped in-base
years, the TARSİM search result and the `ml/REPORT.md` path. These remain true
and are recorded in this document; they were not hiding a negative result. All
payment, dispute and waiting numbers in the UI are unchanged. Browser suite:
13 passed, 2 intentionally skipped.


### Fix blocked demo actions (2026-10-21)

Reported symptom: replay, attack and verification buttons remained disabled.
The local services were healthy; those actions depended on a proposed agreement,
three approvals and revealed reports, without a usable entry at the blocked step.
The UI also loses its in-memory agreement on reload while the chain clock persists.

- Unprepared replay/evidence sections now offer an enabled local-demo entry:
  propose the displayed rule, approve as all three explicitly simulated roles,
  lock the deposit, then start replay. This executes actual local transactions;
  it does not bypass the agreement hash, terms check or contract state machine.
- Partially approved agreements can complete their remaining demo signatures.
  The original individual signing controls are retained.
- If the historical season has already started on the demo clock, the blocked
  section offers an explicit reset action. It never silently resets the chain.
- Before provider evidence exists, attack/verification sections point directly
  to the missing step instead of showing inert attack/verification buttons.
- Contract proposal code is shared by the manual and convenience paths.
  Demo convenience signing is restricted to chain ID 31337.

The new desktop regression starts from step 6, signs and replays, settles a real
source disagreement via fallback, rejects a dropped-evidence bundle, verifies
an intact agreement and checks the reload/reset recovery. No contract, climate
engine, verifier or mobile-specific code was changed.

Validation: production build and TypeScript passed; all six desktop browser
regressions passed. The new blocked-entry regression also passed against the
production build at port 3000. The final demo chain was reset by that test.
Production screenshots confirm the verifier reports success and the evidence
bundle is downloadable. No mobile tests were run this round.

## Season data, provider reports and rule stability (2026-10-21, Claude)

Three design problems found in review, fixed through spec, contract, providers,
UI, bundle and verifier:

- **The signed rule pinned data that could not exist at signing.** It held the
  sha256 of whole download files that include the observation season. Now it
  pins each record's history to 31 December of the previous year (enough for the
  normal and the gap-fill fit) and names the publisher and URL of the season.
  Each provider fetches the season after it ends; its evidence records the
  sha256 of every fetched file, and its on-chain report carries the evidence
  digest. Validation refuses a spec that pins season data; the verifier checks
  both halves. The fetch is simulated by cutting the same October 2026 download
  (`climate/archive.py`). `verify.py --refetch` against NOAA and Open-Meteo
  matched every season value of the recorded Muğla 2021 case.
- **Commit–reveal protected nothing.** Both verdicts are deterministic functions
  of public data and a public rule, so a sealed verdict cannot stop copying.
  `OracleRound` was replaced by `ProviderReports`: one final report per
  designated provider, after the season and before a 14-day deadline; a second
  report is refused (`AlreadyReported`); silence counts as absent. An abstention
  is now a report, so a "too little data" summer opens the dispute at once
  (modelled wait 30 days instead of 44). A full disputed agreement: 8
  transactions and 864,070 gas (was 10 and 990,799).
- **The rule finder over-trusted 30 summers.** It ranked by distance to the
  target count, so it could prefer 10 payments with 10 disputes over 8 with 3.
  Options within 25 % of the target now tie and are ranked by fewer disputes,
  then fewer payments that hinge on one day (shown per option and signed in the
  purpose block). Ranking hinge before disputes was tried first and rejected:
  it promoted a rule whose payments were almost all by fallback. The options
  offered changed in 6 of 12 site/fallback/target settings; Muğla's 1-in-5 "pay" pick (10-day
  rule, 7 of 30) did not.

## Graded payout and partial release (2026-10-21, Claude)

All-or-nothing put the whole deposit in dispute whenever the two records
disagreed, and let one day decide all of it. The signed text now carries a
payout ladder (default graded: 40 % of the deposit at the minimum spell, 70 %
three days longer, 100 % six days longer; a one-step ladder is the old
behaviour). The contract applies it to the spells the providers report: the
share a quorum supports is paid at once, the share a quorum rules out is
returned at once, and only the difference goes to the unanimous vote or the
fallback. With three providers the middle report decides. A report whose spell
contradicts its verdict is refused. The verifier reads the ladder from the
chain and recomputes the split.

Muğla 2021 (station 4 days, ERA5 10): 15,000 DEMO returned at once, 35,000
disputed, instead of 50,000 disputed. Muğla 2025 (6 and 10 days): 20,000 paid
at once, 15,000 disputed, 15,000 returned. Over 1996–2025 the graded ladder
pays about half as much in total for the same deposit and does not always cut
money held in dispute (Muğla 6-day rule: 4.0 deposits either way; Antalya
3.0 → 2.4; Muğla 8-day rule 5.0 → 2.3). In-base years use the median bootstrap
replicate, which reproduces the all-or-nothing verdicts exactly.

The rule finder ranks by money held in dispute (identical order to dispute
counts for all-or-nothing) and shows average payment and the share of deposits
decided by the data alone. The home page shows the split for Muğla 2021 and
cites the real-world context (TARSİM drought payouts, heat cover for citrus,
Red Cross heat protocols).

## Release during the heatwave (2026-10-21, Claude)

Post-season settlement paid relief in October for heat in June. A hot spell
only grows, so a spell already in the published data cannot be undone by later
days. Providers may now file interim "met" reports during the season (the
season published so far, 5 days behind), raising them as the spell grows;
anyone calls `release` and the contract pays the share both providers already
support. Reports can only go up, released money is never taken back, a provider
that files no final report leaves its last interim report standing, and an
interim report is accepted only if filling the rest of the season could not
break the agreed fill limit (found when the "too little data" case released
money early and then abstained). The verifier reads every interim report from
the event log and recomputes it to its date.

Antalya 2024: 35,000 DEMO on 15 June, 15,000 on 22 June, instead of October.
Replay 2021–2025, 10 stations, default graded rule: 96 % of the payout both
records agreed on released before 1 October; first release in June for 6, July
for 4, August for 8 of 19 paying summers (scripts/inseason.py).
