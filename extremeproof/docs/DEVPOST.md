# ExtremeProof — Devpost submission text

**Tagline:** Heat relief agreed before the summer, paid by a rule both weather records can check, verifiable by anyone.

**Links**
- Source: https://github.com/cs113062273-bot/IEEE-ClimateChain-Global-Hackathon
- Static demo (no install): https://cs113062273-bot.github.io/IEEE-ClimateChain-Global-Hackathon/
- Video: _add link_

## Track

**Track 4 — Climate Data & Environmental Monitoring.** The track's problem is "environmental data is fragmented and difficult to verify"; its first suggested build is a climate data verification platform. ExtremeProof verifies the climate statistics behind a heat-relief payment (a place's 30-year normal, its calendar-day thresholds, the hot spells measured against them) and makes the payment follow from data anyone can recompute.

## Inspiration

Climate is the long-run statistics of weather in a place; a heatwave is the hot tail of those statistics. Relief for extremes is increasingly agreed in advance and paid when an index crosses a line. Whether a summer crosses it depends on choices that move money:

- **Which record.** Muğla, Türkiye, summer 2021, a summer of forest fires: the weather station counted a 4-day hot spell, the ERA5 reanalysis 10 days.
- **Which 30 years are normal.** In Muğla the same ERA5 rule flips verdict in 10 summers since 1966 between the 1961–1990 and 1991–2020 normals.
- **How gaps are filled.** The Antalya station reported 31 of 122 days in summer 2024. Two standard gap fills give a 7-day or a 13-day spell.

These choices are usually made and computed by the paying side, and the community cannot check them. In 2016 Malawi's drought cover first failed to trigger because the model assumed the wrong maize variety; the payout came months later.

## What it does

Users: a **relief fund** that deposits the money, a **farmers' cooperative** that represents the people it is for, an **independent checker**, and two **data providers** (station record, ERA5).

1. **Climate.** At 14 stations (10 in Türkiye; Athens, Larissa, Bucharest, Sofia), daily maximum temperature against two definitions of "unusually hot", and 60 summers of hot spells against one fixed line: in Muğla a 6+ day spell happened in 9 of 30 summers in 1966–1995 and 19 of 30 in 1996–2025.
2. **Design the rule by its purpose.** Say how often the community should be paid (about 1 summer in 3, 5 or 10), all-or-nothing or graded (40 / 70 / 100 % of the deposit at 6 / 9 / 12 days), and where unresolved disputes go. The finder compares complete rules on 1996–2025: payment frequency, payments that hinge on one day, deposits held in dispute, and how often the heat met the definition in 1966–95 versus 1996–2025. A decision brief shows what the rule would have done in every summer 2021–2025, and a regional scan applies it at all 14 stations.
3. **Lock.** The rule, the 122 daily thresholds per source and every contract term become one canonical JSON text and fingerprint. The browser recomputes it; the contract's terms are read back against it. The fund, cooperative and checker sign; the fund's signature escrows the deposit; the contract refuses to lock once the season has started. The cooperative can download a one-page member summary in English and Turkish.
4. **The contract reads the heat.** Providers post daily readings on chain. The contract checks the thresholds against the signed fingerprint, compares every reading with that day's threshold and counts the spell itself. Days are append-only, so a spell only grows. Weekly, the share both records already support is released: in Antalya 2024, 35,000 DEMO on 15 June and 15,000 on 22 June. After the season the share neither supports returns at once and only the difference is disputed (unanimous vote, or the signed fallback after 30 days). Muğla 2021: 15,000 returned at once, 35,000 disputed instead of all 50,000.
5. **Try to cheat.** Re-sign with another normal after the season, lower the signed threshold by 2 °C, edit one temperature, flip a verdict, drop the evidence. The contract or the verifier rejects each one, live.
6. **Verify independently.** Download the bundle (signed rule, pinned history, season data each provider fetched, evidence, chain snapshot) and run one standard-library Python file. It recomputes thresholds and every season day, matches the contract's on-chain day log, checks every executed term against the signed text and checks the settlement. `--refetch` compares the season with what NOAA and Open-Meteo serve today.

## How we built it

- **Climate engine** (standard-library Python): ETCCDI calendar-day percentiles (5-day window, Hyndman–Fan type 8), Zhang et al. (2005) bootstrap for in-base years, TX90p, WSDI, seasonal hot spells. Matched xclim 0.58 to within 1e-9 on real station data with gaps.
- **Data:** GHCN-Daily (NOAA NCEI) and ERA5 / ERA5-Land via Open-Meteo, every file pinned by sha256 with URL and retrieval time. The signed rule pins history to 31 December of the previous year and names where the season will be fetched from.
- **AI:** LightGBM gap filling for missing station days, evaluated under a protocol frozen before results against three baselines, judged on whether it keeps trigger verdicts right. It had the lowest daily error (0.97 °C vs 1.07 °C) and still missed 3 of 9 heatwaves, so it was **not adopted**; quantile mapping (9 of 9) is the default.
- **Contracts** (Solidity 0.8.28, Hardhat 3): `TriggerAgreement` (three-party lock, escrow, payout ladder, quorum, in-season release, dispute, fallback) and `SeasonRecord` (daily readings checked against the signed thresholds, spells computed on chain, every day folded into a keccak log). Readings and thresholds are integers in thousandths of a degree. A disputed agreement costs 10 transactions, about 1.7 million gas.
- **Services:** two provider processes with their own keys and a hub that stores specs and assembles bundles (FastAPI, web3.py).
- **Verifier:** an independent re-implementation (percentiles, gap filling, spells, canonical hashing, Keccak) sharing no code with the engine.
- **Web:** Next.js 16 with hand-built SVG charts. A live edition drives the local chain; a static edition on GitHub Pages replays three recorded agreements with their bundles.

## Challenges

- Matching xclim exactly: leap-day handling (365 thresholds mapped onto 366 days) and bootstrap year substitution.
- Station data are thinnest when it matters: Antalya has 48 days of TX in all of 2024. A provider must be able to say "not enough data" without that counting as "no".
- Pinning only what exists at signing. The season's data do not exist on 1 June, so the rule pins history and the season's source; each provider's report binds the files it actually fetched.
- Replaying past summers while the contract still enforces "lock before the season": the local chain starts on 1 May 2021 and its clock moves through the season.

## Accomplishments

- The contract, not a provider, decides whether the heat counted, and the verifier matches its on-chain record day by day.
- Money moves during the season: replaying 2021–2025 at the 10 Turkish stations, in the 19 summers both records supported a payment, 96 % of that money was released before the season ended, in 10 of them by end of July.
- A regional finding from public data: with an all-or-nothing rule, station and ERA5 give opposite answers in 46 of 358 decidable summers in Türkiye and 27 of 180 abroad. At 4 of 10 Turkish stations and at Sofia the public station record is too incomplete to define a 1991–2020 normal, which a station-only scheme would only discover after money was promised.
- Every attack in the demo runs for real against the contract or the verifier.

## What we learned

The "objective" part of a parametric trigger, the climate statistics, hides judgement calls that move real money. Making them explicit, fixed before the season and recomputable matters more than any single model. For triggers the right AI objective is the tail, not the mean.

## Scalability and adoption

- The rule needs a station ID and a grid point. GHCN-Daily and ERA5 are free and global; the same code runs unchanged at the 4 stations outside Türkiye.
- One agreement is a handful of transactions; checking it is one Python file.
- Possible users: Red Cross heatwave protocols that already release money at a threshold (Greece 2024, Kyrgyzstan 2025), relief funds, farm insurance pools and cooperatives that pay on a heat index.
- Next: rainfall and drought indices (Rx5day, CDD, SPI), a third independent provider and 2-of-3 quorum, public testnet deployment with a decentralised oracle for provider transport, and a pilot with an anticipatory-action programme.

## Built with

Python, xclim, LightGBM, FastAPI, web3.py, Solidity, Hardhat, viem, Next.js, TypeScript, GHCN-Daily, ERA5, Open-Meteo, GitHub Pages.

## Limits

Adaptation, not mitigation: it does not reduce emissions. Pre-arranged relief, not insurance. Observed heat only, never a forecast. Parties, providers, DEMO money and the chain clock are simulated locally; no real users yet. Provider A fills station gaps with ERA5, provider B's source, so the two are not fully independent. A provider's report proves which bytes it used, not that the publisher served them. The payout ladder is an editable example, not calibrated to loss data. A blockchain does not make data true.
