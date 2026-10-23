# GridProof workplace charging: product, method and evidence

October 19, 2026. `http://127.0.0.1:3000` now opens the workplace car-park workspace. The previous fleet readiness planner (`/readiness`) and research pages (`/research`, `/dispatch`, `/replay`, `/audit`) are archived: unlinked from the product and bannered, kept for the recorded proofs, offline backup and their tests. Nothing was deployed, submitted or published.

## The decision this product supports

**User:** the facilities or energy manager of a staff car park whose chargers share one capped grid connection (a transformer, a building supply or a connection agreement).

**The job:** every working day, 20 to 50 drivers plug in between about 06:00 and 10:00 UTC and leave between 13:00 and 18:00. Together they want more power in the morning than the connection can give. Someone has to wait. The manager is judged on two things: drivers leaving with the charge they asked for, and never exceeding the connection limit. Carbon and cost come after that.

**Inputs at each half-hour:** which cars are plugged in, how much energy each asked for, each driver's history of earlier sessions, the connection limit and building load, and a past-only grid carbon forecast. Not available: when each driver will actually leave, and who will arrive later.

**Success:** share of drivers whose request was met in full by departure, energy left undelivered, half-hours over the limit (must be zero), then modelled carbon, illustrative cost and peak.

**Bigger decision:** how large a connection the site needs for a given service level. Connection capacity is a common bottleneck for workplace and fleet electrification, so a controller that serves the same drivers on a smaller connection lets more chargers fit before an upgrade.

## Why the direction changed

The inherited product promised "full energy three hours after arrival" for two simulated vehicles and reported 122/122 completed days. Reading the code showed that number is deterministic. With the zero-solar capacity guard, nothing that decides feasibility (building load, job list, battery, connection) varies by day, so one feasibility check was repeated 122 times. The real service risk, real drivers leaving at uncertain times, was never tested. The LightGBM carbon forecast also had no resolved carbon value over a seasonal median. The blockchain layer had no counterparty that needed it.

What the evidence did support: under a cap, the biggest lever is **who gets power first**, and that depends on predicting departures. A public dataset made this testable on real behaviour, with a genuinely unseen year.

## Data

| Source | Use | Licence and handling | Time range and quality |
|---|---|---|---|
| de Bont et al. (2025), *Electric Vehicle Charging Session Data of Large Office Parking Lot*, 4TU.ResearchData v2, [doi:10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2](https://doi.org/10.4121/80ef3824-3f5d-4e45-8794-3b8791efbd13.v2) | Real arrival, departure, delivered energy and pseudonymous driver ID; departure model training; replayed days | CC BY-NC-SA 4.0, non-commercial. Downloaded by `scripts/fetch_workplace_sessions.py` (no account), MD5 checked against the repository listing, SHA-256 pinned in `data/trust/carpark_anchors.v1.json`. Not redistributed: the README asks users to consult the contacts before sharing transformed data, so session-level derivatives and the trained model stay in gitignored `data/`. | 55,379 sessions, 2020-08-25 to 2024-10-02, Utrecht office car park (~300 charge points). Local Amsterdam times converted to UTC; 0 ambiguous times, 0 sessions crossing UTC midnight. The source already removed sessions under 1 kWh, under 10 minutes or over 24 hours. 20 shared roll-out IDs are treated as unknown drivers. From March 2023 a controller managed most of the employee deck, so delivered energy there can be lower than demand; dwell times are behaviour. COVID periods in 2020–21 are in the training years only. |
| NESO national carbon intensity 2025; Open-Meteo ERA5 London radiation 2025 | Grid days for replay: past-only seasonal carbon forecast for decisions, actual intensity and radiation-derived PV for scoring | Existing pinned snapshots and anchors, unchanged | Two incomplete days (2025-01-13, 2025-08-11) excluded with reasons |

**Site:** rails E and M, which share one transformer per the dataset README (17,578 sessions overall). **Grid pairing:** session day D is replayed on the GB grid day with the same weekday (2023 +728 days, 2024 +364 days). This is a constructed scenario: Dutch driver behaviour, British grid conditions, a synthetic campus building load (6 kW night, 14 kW day) and an illustrative tariff. **Decision-time availability:** departures are known only once they happen; driver features use sessions on strictly earlier dates, so same-day sessions never see each other. Requests are the sessions' delivered energy, assumed declared at plug-in, and capped to what the car could physically receive when connected for whole half-hours. Both use the real departure, so they are simulation set-up, not decision inputs: in the 2024 test days 383 of 5,671 sessions (6.8%) were capped, 15 had nothing servable and were dropped, and 97 were given a power limit above 11 kW because their real average rate was higher. Every policy sees the same set. A met request means that session's energy was delivered, not that a battery was full (the data has no state of charge).

## Method

**Departure risk (the ML that matters here).** For each plug-in, LightGBM quantile regression predicts the dwell time at 8 levels (2% to 90%) from the arrival time, weekday and that driver's earlier sessions (median, 10th/25th percentile, spread, last five, typical departure clock time, same-weekday median, days since last visit). Delivered energy is excluded because it depends on how long the car stayed. Quantiles are rearranged to be monotone, then each level gets a conformal shift so that, on the calibration window, the stated share of drivers leaves before it. The ablation is the same pipeline with arrival hour only.

**Controller.** Every half-hour the controller sees only cars plugged in by the slot start. *GridProof priority* charges cars in order of their ready-by target (the calibrated 20% departure quantile: by then, about 80% of similar plug-ins are still connected), each at up to 11 kW, until the connection headroom with **zero solar** is used. Executed energy is never revisited. *Carbon-flex* is an LP over the rest of the day that minimises carbon, cost, peak and the **expected undelivered energy under each car's departure distribution**, re-solved whenever the connected set changes. *Equal share* is industry-default dynamic load balancing.

**Operator changes.** A grid operator's limit for a future window, or a driver declaring that they must leave at a given time, is applied from the slot it is announced. Earlier slots are untouched (tested). At every half-hour the product also computes an exact lower bound: given the cars connected now, the minimum energy that no schedule can deliver by their ready-by targets (an LP; later arrivals can only make it worse).

## Evaluation protocol

[`experiments/carpark/protocol.json`](../experiments/carpark/protocol.json) was written before any 2024 simulation. Model fitted on 2021–2022 sessions; conformal shifts from 2023 H1; every choice (EDF or least-laxity, personal or population model, promise level, LP risk penalty and hard promise) made on 2023 H2 by the declared rules; 2024 evaluated once. `scripts/evaluate_carpark.py --stage test` refuses to run if the protocol or model changed after selection. After a line-ending normalisation the frozen pipeline was re-run; all 32,566 numeric result rows were identical apart from wall-clock timing.

Selected: **earliest-promise-first with the personal model at the 20% quantile** (mean 98.33% of requests met in full over 100–160 kW on 2023 H2; best population-model variant 95.90%). Carbon-flex: risk penalty 3, no hard promise.

## Results on the held-out year (185 weekdays, 5,656 real sessions)

| Connection needed for... (10 kW steps) | ≥95% of requests met in full | ≥98% | ≥99% |
|---|---:|---:|---:|
| Equal-share load balancing | 160 kW | >200 kW | >200 kW |
| Priority, population model | 150 kW | 180 kW | 200 kW |
| **GridProof priority** | **130 kW** | **150 kW** | **170 kW** |
| Priority knowing true departures (not deployable) | 110 kW | 120 kW | 130 kW |

| At 120 kW | Requests met in full | Energy short | kgCO₂/day | g/kWh delivered (site) | £/day |
|---|---:|---:|---:|---:|---:|
| Equal share | 88.30% | 4.77% | 108.10 | 167.7 | 177.80 |
| **GridProof priority** | **94.61%** | **2.56%** | 110.08 | 166.9 | 181.42 |
| Priority, population model | 87.34% | 5.21% | 107.88 | 168.1 | 177.11 |
| Carbon-flex | 89.09% | 3.45% | 108.36 | 165.8 | 182.19 |
| Uncontrolled (ignores the limit) | 100% | 0% | 115.15 | 170.1 | 184.67, over the limit in 874 half-hours |

Paired by day at 120 kW, GridProof priority meets **+1.93 more drivers' requests in full per day** than equal share (moving-block 95% CI 1.58 to 2.28; better on 120 days, worse on 1) and delivers 14.9 kWh/day more. Against the population model it is +2.22 drivers/day (CI 1.70 to 2.75; 109 better, 5 worse): **the personal departure model is the value**, and the population model alone is worse than equal share. Calibration held: on 2024 site sessions, 10.1% left before the predicted 10% quantile and 20.2% before the 20% target.

The full tables, all paired differences, every day GridProof did worse (15 at 100 kW, 1 at 120 kW, 2 at 150 kW) and the sensitivity study are in the [derived report](../experiments/carpark/REPORT.md).

**Carbon, honestly.** Priority charging raises modelled emissions (+1.98 kg/day at 120 kW, CI 1.42 to 2.54) because it delivers more energy; per delivered kWh the site intensity is essentially unchanged. Carbon-flex at 150 kW cuts modelled emissions 1.1% versus equal share at the same service (−1.22 kg/day, CI −1.56 to −0.82; served difference −0.02 drivers/day, CI −0.23 to +0.20) for +£2.58/day, but meets 1.31 fewer drivers' requests in full per day than priority. With true departures the LP still does badly at tight caps (67.5% of requests met in full at 100 kW): it is myopic about arrivals it cannot foresee and leaves morning capacity idle. Load shifting at a workplace needs better departure and arrival information before it is worth recommending. These are national-average, location-based exposures, not causal avoided emissions.

**Sensitivity (frozen policies, 2024).** GridProof priority stays ahead of equal share when every car is limited to 7.4 kW (94.50% vs 84.00% at 120 kW), when building load doubles (89.55% vs 83.10%), when each car becomes visible 30 minutes late (93.28% vs 84.99%) and when requests are unknown (95.01% vs 88.30%).

**Remaining failures.** Drivers who leave much earlier than their history suggests are still short; at 100 kW 15.1% of drivers leave short with GridProof versus 21.3% with equal share. First-time drivers fall back to the population prediction. All chargers are assumed to work, every car is assumed to accept 11 kW, presence is counted in whole half-hours, and there is one site and one operator population.

## Post-review checks (exploratory)

Two external reviews asked whether the gain depended on inputs derived from the real departure, and whether LightGBM beats a simple estimator using the same personal history. Both were tested under a separate protocol ([`experiments/carpark_followup/protocol.json`](../experiments/carpark_followup/protocol.json)), selecting each model family on 2023 H2 and evaluating on 2024. Because 2024 had already been examined, these are exploratory checks; the published results above are unchanged. Full tables: [follow-up report](../experiments/carpark_followup/REPORT.md).

**Decision-time inputs.** Every car is limited to 11 kW and declares its request at plug-in; nothing is capped or dropped. 380 of 5,671 requests (6.7%) could not be met before the real departure by any schedule, so no policy can exceed 93.3%. GridProof (the pre-registered configuration) meets 88.6% of requests in full at 120 kW versus 85.8% for equal share: **+0.88 drivers per day (CI 0.61 to 1.17; better on 80 days, worse on 17)**, about half the pre-registered gain. It is also positive at 100 kW (+0.77, CI 0.43 to 1.09) and 150 kW (+0.36, CI 0.20 to 0.52), and when the controller knows only each driver's typical past request (+0.96 at 120 kW). For 90% of requests met in full it needs 130 kW versus 150 kW. At an extremely tight 80 kW it is slightly below equal share (62.4% vs 63.2%). **The product now uses these decision-time inputs.**

**Simple personal history.** A plain quantile of each driver's own past stays, or a shrinkage of it toward the arrival-hour population, recovers almost all of the gain. LightGBM minus the simple personal quantile is +0.12 drivers per day at 120 kW (CI −0.01 to +0.25) and +0.04 at 150 kW (CI −0.05 to +0.12); only the re-selected LightGBM is ahead of shrinkage at 100 kW. Arrival time alone is clearly worse (simple personal quantile +1.22 per day at 120 kW against it, CI 0.87 to 1.56). The product's own configuration is not ahead of the simple personal quantile even at 100 kW (−0.09, CI −0.39 to +0.21). LightGBM stays because both validation selections picked it, but the supported claim is **personal history**, not the model.

**Carbon-flex under decision-time inputs** meets fewer requests in full than equal share at 100 kW (−0.44 per day) and 150 kW (−0.32), for about 1% lower modelled emissions at 150 kW. It is now labelled experimental and not recommended in the product.

## Evidence and trust

Each replayed day can be exported as a canonical record that separates what the controller knew (cars at plug-in, requests, ready-by targets, events, forecasts), what happened (departures, actual carbon, PV) and what it did (energy per car per half-hour). `scripts/verify_carpark.py` uses only the Python standard library and reports four layers:

| Layer | What it proves | What it does not |
|---|---|---|
| Integrity | These exact canonical bytes have this SHA-256 | Anything about the world |
| Physics and service | Zero-solar cap, presence, power limits, energy accounting, metrics arithmetic | That a charger executed it |
| Decision replay | For priority and equal share: re-running the policy from decision-time inputs reproduces every kWh, so decisions could not have used future departures beyond what the record states | LP decisions (constraint-checked only); that the ready-by targets came from the stated model (committed by fingerprint, not recomputed) |
| Source correspondence | Grid values match pinned NESO/ERA5 bytes; every session matches the pinned raw file | That the upstream measurements are true; available only where the licensed raw file is present |

Three built-in forgeries, all re-hashed: adding the missing energy to a short driver fails physics and replay; moving a departure two hours later, or leaving the short drivers out of the day, and recomputing everything consistently passes integrity, physics and replay, and **only source correspondence rejects it** (it checks both that every listed car is a real site session and that every servable site session that day is listed). The completeness check was added after an external review reproduced a 34-to-1 omission that passed all four layers. A record also carries an explicit "not proven" list.

The optional registry is the existing local EVM contract with one active record per site, day and category. It matters only when a counterparty, such as a grid operator settling a flexibility request or an auditor, should see one append-only commitment that neither side can quietly replace. A signed database is enough inside one organisation, and this local chain is a demonstrator, not that shared deployment.

## Run and reproduce

```powershell
.venv/Scripts/python.exe scripts/fetch_workplace_sessions.py   # public, no account; also run by setup
.venv/Scripts/python.exe scripts/run_demo.py                    # http://127.0.0.1:3000
.venv/Scripts/python.exe scripts/evaluate_carpark.py --stage validate
.venv/Scripts/python.exe scripts/evaluate_carpark.py --stage test
.venv/Scripts/python.exe scripts/sensitivity_carpark.py
.venv/Scripts/python.exe scripts/report_carpark.py
.venv/Scripts/python.exe -m pytest backend/tests/test_carpark.py -q
npm --prefix frontend run test:e2e -- tests/carpark.spec.ts
```

The first API request builds the departure model (about 15 s, cached in `data/processed/carpark`). A replayed day with all comparisons is recomputed in about 0.3 s.

## Competitive judgement

The strongest case: a concrete operational decision, tested on real driver behaviour in a year that was never used to choose anything, re-checked with decision-time inputs after external review, with the contribution of personal departure history isolated and statistically clear, a product that shows exactly what the controller knew at each half-hour, and a record whose forgery checks catch a consistent lie only through source correspondence.

The largest weaknesses: the decision-time gain is modest (+0.88 drivers a day at 120 kW, about 3 percentage points) and the model-specific advantage over simple personal history is unproven; one site with Dutch behaviour on a British grid, simulated chargers and building load, no field trial or real operator, and a carbon result that is neutral for the default policy and small for carbon-flex. The climate argument is enablement (more drivers served per kW of connection), not measured abatement. The capacity figures come from 10 kW steps on one replayed site and are planning signals, not connection design values. The comparison set also lacks a simple personal-history baseline (for example the driver-shrinkage quantile already in `departure.py`) under the same rule, so LightGBM's advantage over a simpler personal model is not yet shown; only the value of personal history is.
