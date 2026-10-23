# Gap-filling evaluation: does the AI keep heat-trigger verdicts right?

**Bottom line.** For stations with a history, like Antalya, the AI (LightGBM) is **not adopted**. Quantile-mapped ERA5 is the default gap-filling rule, because it got every pre-registered trigger verdict right (9 of 9) and the AI did not (6 of 9). The AI had the *lowest average error* and still missed three heatwaves. For stations with no history, the pre-registered rule favoured the AI, but a post-hoc check contradicts it, so ExtremeProof does not offer a "no station history" mode. The evidence is thin throughout: 9 pre-registered cases from 3 station-summers, all of them real heatwaves.

Reproduce: `extremeproof/.venv/Scripts/python -m extremeproof.ml.evaluate` → `ml/report.json` (all numbers below).

## Question and protocol

When a station's daily maximum temperature (TX) is missing, which agreed estimate keeps the heat-trigger verdict closest to what the station itself would have reported?

The protocol was written before any results: [protocol.json](protocol.json), sha256 `31455daad06771f6a424849676e6d3250c3c197e3f208b7fd30e845d3679e5cb`. It fixes the candidates, features, splits, metrics and the adoption rule.

- **Candidates.** Baselines: raw ERA5; ERA5 with a per-month linear correction; per-month quantile mapping of ERA5 onto the station. AI: LightGBM (L1 loss) on ERA5 TX of the day before, the day and the day after, ERA5 TN, ERA5-Land TX, and day of year (plus elevation difference in the spatial design).
- **Temporal design.** Per station: fit on 1963–2010, test on 2011–2025.
- **Spatial design.** A model pooled from the other stations is tested on a held-out station.
- **Layer 1.** Daily error on all test days and on the station's hottest 10 % of June–September test days.
- **Layer 2, the decision metric.** Take a station-summer (2011–2025) with no missing June–September days and erase days using three patterns: the days Antalya actually lost in 2023 (72) and 2024 (91), and the whole season (122). Fill the erased days with each method, then apply the heat rule (6+ days above the station's own 1961–1990 calendar-day 90th percentile; stations need 60 % base coverage). Compare the verdict and longest spell with those from the real data.
- **Adoption rule.** Adopt the AI only if it has strictly more layer-2 verdict agreements than the best baseline and no larger longest-spell error.

### Deviation from the protocol

Mersin (TUM00017340) and İzmir (TUM00017220) appear in the GHCN inventory from 1974 and 1950, but they have only 19 and 21 station days before 2011. They cannot be fitted per station, so they are excluded from the temporal design. They stay in the spatial design, as held-out test stations and as training data for the others. This was found when the first run failed for lack of data, before any results for these stations existed.

## Results — pre-registered

### Layer 2: trigger verdicts (decision metric)

Only 3 station-summers met the eligibility rule: Finike 2011 and 2021, and Isparta 2015. With 3 gap patterns each, that makes 9 cases. All 3 summers were real heatwaves, so this test can detect **missed** triggers but **not false ones**.

| Method | Temporal: verdicts right | missed | longest-spell error (days) | Spatial: verdicts right | missed | longest-spell error (days) |
|---|---|---|---|---|---|---|
| Raw ERA5 | 2 / 9 | 7 | 4.22 | 2 / 9 | 7 | 4.22 |
| Linear-corrected ERA5 | 6 / 9 | 3 | 0.67 | 2 / 9 | 7 | 4.89 |
| **Quantile-mapped ERA5** | **9 / 9** | **0** | **0.67** | 2 / 9 | 7 | 4.89 |
| LightGBM | 6 / 9 | 3 | 1.22 | **7 / 9** | 2 | 1.56 |

Decision under the rule: **temporal → quantile mapping (AI not adopted)**; spatial → AI adopted (7 vs 2), on 9 cases.

### Layer 1: daily error (mean over stations, °C)

| Method | Temporal: all days | Temporal: hot days | Spatial: all days | Spatial: hot days |
|---|---|---|---|---|
| Raw ERA5 | 1.37 | 1.88 | 1.44 | 1.97 |
| Linear-corrected ERA5 | 1.01 | 1.55 | 1.48 | 2.44 |
| Quantile-mapped ERA5 | 1.07 | **1.14** | 1.51 | 2.19 |
| LightGBM | **0.97** | 1.38 | **1.35** | **1.70** |

## Results — post-hoc, exploratory (not used for any decision)

This check was added *after* seeing the results above, to get more summers: the 1991–2020 base, scored on 2021–2026 (outside that base). It yields 4 station-summers (Finike and Muğla, 2021 and 2026), so 12 cases, which now include summers *without* a heatwave.

| Method | Temporal: right | false | missed | spell error | Spatial: right | false | missed | spell error |
|---|---|---|---|---|---|---|---|---|
| Raw ERA5 | 10 / 12 | 0 | 2 | 2.83 | 10 / 12 | 0 | 2 | 2.83 |
| Linear-corrected ERA5 | 11 / 12 | 1 | 0 | 1.17 | 10 / 12 | 0 | 2 | 3.42 |
| Quantile-mapped ERA5 | 11 / 12 | 1 | 0 | **0.58** | 10 / 12 | 0 | 2 | 3.25 |
| LightGBM | 10 / 12 | 2 | 0 | 1.25 | 8 / 12 | **4** | 0 | 1.42 |

- **Temporal.** Quantile mapping is again best, with the smallest spell error. This is consistent with the pre-registered decision.
- **Spatial.** The AI drops to last place with 4 false triggers, contradicting the pre-registered spatial result. We therefore do not rely on the AI for stations without a history.

## What we learned (failure analysis)

- **Lowest average error ≠ right trigger.** LightGBM is trained to minimise absolute error, so it predicts something like the conditional median and pulls hot days toward typical values. Its hot-day bias is negative at 7 of 8 stations in the temporal design; at Adana it is −2.8 °C. Pulled-down hot days break spells, which caused 3 missed heatwaves. Linear correction has the same problem. Quantile mapping preserves the tails of the station's distribution, which is exactly what an exceedance count needs.
- **Raw ERA5 is not a gap filler.** At Finike it is 5 °C cooler than the station on hot days (hot-day error 4.96 °C), so filled days rarely exceed the station's own threshold. At Antalya it runs warmer in summer. Using raw ERA5 trades one source's bias into the other's threshold.
- **Without a station history, nothing works reliably.** In the spatial design the fitted corrections lose most of their benefit: hot-day error rises from 1.14 to 2.19 °C for quantile mapping and from 1.55 to 2.44 °C for linear correction. The two analyses disagree on which method is least bad.
- **The data are thin exactly where it matters.** Only 3 (pre-registered) or 4 (exploratory) complete station-summers exist among 10 Turkish stations in 2011–2026. That is the same gap problem the product addresses, and it limits how strongly any method can be validated.

## What the product does with this

- The default rule in the demo and in `climate/specs.py` is **station + quantile-mapped ERA5**, fitted only on years before the observation year. Linear correction and raw ERA5 stay available in the backtest so parties can see how much the choice matters.
- The trigger is **always** the published rule; no model decides whether a heatwave happened.
- A rule can cap how many days may be filled (`max_filled_days`). Past that cap, the provider abstains instead of guessing.
- `lightgbm_antalya.txt` is the temporal model for Antalya, kept only for reproducibility. It is not used by any provider.
