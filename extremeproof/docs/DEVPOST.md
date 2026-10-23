# Devpost submission draft — ExtremeProof

> Draft only. Not submitted. Fill in the video link and public repository URL before submitting.

**Tagline:** Was that heatwave really extreme — for this place? Climate statistics for pre-arranged relief, fixed before the season, settled by independent data, checkable by anyone.

## Track alignment

**Track 4 — Climate Data & Environmental Monitoring.** The track's problem statement is "Environmental data is fragmented and difficult to verify"; its first suggested build is a climate data verification platform. ExtremeProof verifies the climate statistics themselves — a place's 30-year normal, its calendar-day percentiles and the hot spells measured against them — and makes the decision that depends on them (paying out relief) follow from data anyone can recompute.

## Inspiration — the climate problem

Climate is the long-run statistics of weather in a place (IPCC AR6; WMO uses 30-year normals). Heatwaves are the hot tail of those statistics. Relief for climate extremes is increasingly agreed in advance and paid when an index crosses a line — but whether a summer crosses it depends on which 30 years count as normal, which thermometer is trusted, and how its gaps are filled. In Antalya, the COP31 host city:

- with the same rule and the same reanalysis, 9 summers since 1966 change verdict depending only on whether the normal is 1961–1990 or 1991–2020;
- the station reported only 31 of 122 days in summer 2024, and two standard ways of filling the gaps give a 7-day or a 13-day hot spell.

Those choices are usually computed by the paying side, and the people the money is for cannot check them. In 2016 Malawi's drought cover first failed to trigger because the model assumed the wrong maize variety; the payout came months later.

## What it does

1. **See the normal move.** Daily maximum temperatures against two definitions of "unusually hot" for a place, from GHCN-Daily stations and ERA5.
2. **Design the rule and backtest the agreement** on 61 summers (1966–2026): gap filling, base period, percentile, minimum spell, data limits and dispute fallback. The backtest shows what the 2-of-2 agreement would have done each summer — pay, refund or dispute — and why, before anyone signs.
   **Or start from the purpose.** Say how often the community should be paid (about 1 summer in 3, 5 or 10, counting payments made by the dispute fallback). ExtremeProof searches 32 complete rules and compares the best ones on payment frequency (split into by agreement and by fallback) now and in the last 10 summers, disputes, how long the deposit waits, and how often the heat met each definition in 1966–1995 versus 1996–2025, with the spells that explain every difference. Thirty summers hold only a handful of payments, so for every option it also shows how many payments **hinge on one day** (paid with no day to spare, or missed by one); options within about 25 % of the target count as equally close and are ranked by fewer disputes, then fewer hinging summers. The chosen target, its calibration and the hinge counts are signed with the rule.
   **Then the same rule at 10 stations.** Each place keeps its own normal. Under the default rule, station and ERA5 give opposite answers in 46 of 358 decidable summers (13 %) across 6 places; in the other 4 the public station record holds under 60 % of 1991–2020, so a station-only scheme could not run at all. Any of the 10 can be signed and settled.
3. **Lock it.** The rule and every term the contract will execute (parties, amount, quorum, provider per source, windows, data limits, fallback) become one canonical-JSON text and fingerprint. It pins only what exists at signing — each record's history up to 31 December, by sha256, and the climate statistics computed from it: **the "unusually hot" threshold for each of the 122 season days, per source**, whose fingerprint the contract stores — and names the publisher and URL the season will be fetched from, because that data does not exist yet. A relief fund, a community representative and an independent checker sign that fingerprint; the fund's signature deposits the money. The UI proposes only from the signed text and reads the terms back from the chain. The contract refuses to lock once the season has started; a locked rule cannot be edited. Before signing, the cooperative can download a one-page plain-language summary of the rule in English and Turkish, generated from the exact text to be signed.
4. **The contract reads the heat.** Two provider services (station and ERA5) post the season's **daily readings** on chain. The contract checks the thresholds they use against the signed fingerprint, compares every reading with that day's threshold, and counts the hot spell, filled and missing days itself — a provider cannot claim a spell its own readings do not show. Days are append-only and a day that has not ended cannot be posted, so a spell only grows: during the season providers post newly published days when they lengthen the spell, and anyone can release the share both providers' readings support. In Antalya 2024 the full 50,000 DEMO reached the cooperative on 15 and 22 June instead of after 30 September. Replaying 2021–2025 at all 10 stations, 96 % of the money both records agreed on would have been released before the season ended, in 10 of the 19 paying summers by the end of July. After the season each provider posts the rest of the season with the digest of its evidence, which names every file it fetched. The payout is graded by spell length (40 / 70 / 100 % of the deposit, adjustable): the contract pays at once the share both support, returns at once the share neither supports, and sends only the difference to a dispute that only all three parties together, or their pre-agreed fallback, can resolve. Muğla 2021 (station 4 days, ERA5 10): 15,000 DEMO returned at once, 35,000 disputed instead of all 50,000. Every step shows its transaction hash, block, gas and decoded events, read back from the receipt (a full disputed agreement: 10 transactions, about 1.7 million gas).
5. **Try to cheat** — change the base period afterwards, have a provider lower the signed "unusually hot" line by 2 °C to stretch the heatwave, edit a fetched reading, flip a verdict, drop the evidence — and watch the contract or the verifier catch it.
6. **Verify independently.** Download a bundle (rule, pinned history, the season data each provider fetched, evidence, chain snapshot) and run one standard-library Python file; with `--refetch` it also compares the season with what NOAA and Open-Meteo serve today. It recomputes the signed thresholds and every season day, checks that the readings on chain are exactly those days (the contract's day log), recomputes every verdict, checks every executed term against the signed text, accounts for every provider on chain (a missing proof fails; a justified abstention passes) and checks the settlement.

## How we built it

- **Climate engine** (standard-library Python): ETCCDI calendar-day percentiles (5-day window, Hyndman–Fan type-8), Zhang et al. (2005) bootstrap for years inside the base period, TX90p, WSDI and seasonal hot spells. Cross-validated against **xclim 0.58** on real station data with gaps — agreement better than 1e-9.
- **Data:** GHCN-Daily (NOAA NCEI) and ERA5 / ERA5-Land via Open-Meteo, each download pinned by sha256 with URL, retrieval time and licence. The signed rule pins history to the end of the previous year; the season is fetched afterwards (simulated in the demo from the same pinned download).
- **AI:** a LightGBM gap-filling model for missing station days, evaluated under a protocol frozen before results against three baselines, on whether it keeps *trigger verdicts* right — not just average error. It had the lowest average error and still missed 3 of 9 heatwaves, so it was **not adopted**; quantile mapping (9 of 9) is the default. Lesson: for triggers, the right objective is the tail, not the mean. ([report](../ml/REPORT.md))
- **Contract** (Solidity 0.8.28, Hardhat 3): `TriggerAgreement` (three-party lock, escrow, payout ladder, quorum, disputes, fallback) and `SeasonRecord`, which takes the daily readings, checks them against the signed thresholds and computes the spells on chain, folding every day into a keccak log. Readings and thresholds are integers in thousandths of a degree (thresholds rounded down); on about 500,000 station and ERA5 summer days this gives exactly the same hot days as the real-number engine. An earlier version had providers assert their verdict behind a commit–reveal; we replaced both, because the verdict is arithmetic on public data — the contract can do it, and sealing it hides nothing.
- **Services:** two provider processes with their own keys, a hub that only stores specs and assembles public bundles, all in FastAPI + web3.py.
- **Verifier:** an independent re-implementation (percentiles, fills, spells, canonical hashing, Keccak for ABI selectors) that shares no code with the engine; 60 parameter combinations agree with the engine exactly. Against the real publishers (`--refetch`), every season value of the recorded Muğla 2021 case matched.
- **Web:** Next.js 16, hand-built SVG charts with tooltips, table views and dark mode.

## Challenges

- Matching xclim exactly meant reproducing its leap-day handling (365 thresholds stretched onto 366 days) and its bootstrap year substitution.
- Station data are thin exactly when it matters: Antalya has 48 days of TX in all of 2024. A provider must be able to say "not enough data" without that becoming "no".
- Replaying a past summer while still enforcing "lock before the season": the local chain starts on a simulated date and the clock moves forward through the season.
- Not pinning what cannot exist yet. A first version put the hash of the full data file, season included, into the signed rule — impossible to compute on 1 June. The rule now pins only history and names the season's source; each provider's report binds the season data it actually fetched.

## Accomplishments

- A verdict that three implementations (engine, xclim, verifier) agree on.
- A regional finding from public data: in 4 of 10 Turkish GHCN stations the record is too incomplete to define a 1991–2020 normal, which a single-source scheme would only discover after money was promised.
- Every attack in the demo runs for real against the contract or the verifier.
- Honest scope: the planning notes contained several wrong numbers; recomputation corrected them before they reached the pitch ([FACTS.md](FACTS.md)).

## What we learned

The "objective" part of a parametric trigger — the climate statistics — hides judgement calls that move real money. Making those calls explicit, early and recomputable matters more than any single model.

## What's next

- Rainfall and drought indices (Rx5day, CDD, SPI) for flood and drought relief.
- More independent providers (national met service, a second reanalysis) and a 2-of-3 quorum.
- Public testnet deployment and Chainlink Functions or a similar decentralised oracle for provider transport.
- Pilots with an anticipatory-action programme and a farmers' cooperative to test the rule-design step with real users.

## Built with

Python, xclim, LightGBM, FastAPI, web3.py, Solidity, Hardhat, viem, Next.js, TypeScript, GHCN-Daily, ERA5, Open-Meteo.

## Honesty notes

Adaptation, not mitigation — it does not reduce emissions. Scope is observed heat: money moves as published data show a spell, never on a forecast. Provider A fills station gaps with ERA5, provider B's source, so the two are not fully independent observations. Parties, providers, money (DEMO units), the chain clock and the post-season fetch are simulated locally; there are no real users yet. A provider's report proves which bytes it used, not that the publisher served them. The default graded ladder is an example the parties can change before signing; it is not calibrated to loss data. A blockchain does not make data true. Not an insurance product.
