# GridProof: service-first product iteration

2026-10-19. The main entry at `http://127.0.0.1:3000` is now a campus fleet readiness workspace. The original multi-policy research interface remains at `/research`, `/dispatch`, `/replay` and `/audit`. No public deployment, account action or contest submission is part of this work.

## Product judgment

The strongest core is a **service-constrained decision with independently checkable evidence**: a facilities manager must have vehicles ready, limit grid imports, and explain the operational tradeoff to a sustainability reviewer. The meaningful differentiator is the connection between the service promise, actual dispatch and the evidence that can challenge it. Hashes, a model name, a digital-twin illustration and an optimizer separately do not solve that job.

The previous product's three most consequential weaknesses were incomplete early-departure service, confusion between retrospective fallback and deployable control, and a screen hierarchy that made technical machinery easier to find than the operator's promise. The new entry prioritizes one workflow: **declare earliest departure → inspect service and tradeoffs → update a request without rewriting executed actions → independently check the same plan**.

The [official judging criteria](https://ieee-climatechain-hack.devpost.com/) were checked on October 19: Climate Impact, Innovation & Creativity, Technical Execution, Practical Usefulness, and Presentation & Communication. Their product interpretation here is useful service, honest modeled climate impact, executable handling of failure, and legible decisions. No inferred numerical rubric or ranking probability is assigned.

Ready-by scheduling is established practice, as illustrated by [ev.energy's product explanation](https://support.ev.energy/en/support/solutions/articles/80001150399-how-does-smart-charging-work-). Adaptive scheduling and MPC also have substantial prior work, including [Caltech's ACN framework](https://arxiv.org/abs/2012.02636). GridProof does not claim to invent either. Its case for competition is a coherent, demonstrable implementation with unusually explicit service and evidence limits. Those external products and papers were read, not independently benchmarked against this prototype.

## User, inputs and success

Primary user: the facilities manager of a small campus fleet sharing chargers, PV and a stationary battery with campus loads. Inputs are a historical grid day, battery capacity, energy requests, arrival times, and earliest acceptable departures. The default fleet needs 24 kWh from 07:00 and 18 kWh from 08:00, with a full-energy service floor three hours after each arrival. The lab's 20 kWh contiguous batch remains mandatory. All times are UTC.

Success means all promised EV energy and lab work are delivered within the declared constraints, then carbon exposure, illustrative cost and peak are assessed. A low-carbon schedule that fails service cannot count as a successful saving. The UI displays the actual numerical shortfall or an explicit necessary capacity bound, and separates revised requests from accepted plans.

Design thesis: a calm utility workspace in slate white, navy and one cobalt action color; the distinctive visual is a departure timeline with energy bars and a hard deadline marker. Two font families cover interface text and time/data. The first screen shows the promised energy and ready times. Tabs switch between the same plan's scheduling, event response and evidence. Motion is limited to computation status, result arrival and control affordances; reduced motion is honored. No decorative energy animation is needed.

## Executable mechanisms

**Declared early service.** A protected request converts the earliest acceptable departure into the EV's hard deadline. The full requested energy is the minimum floor; this version does not estimate a probabilistic departure distribution or promise arbitrary unknown departures. `protect()` produces ordinary explicit scenario constraints, so the original independent physical verifier also checks these deadlines.

**Decision-time boundary.** The new service path passes `decision_view()` to the solver and simple baselines. It removes outcome irradiance/PV and replaces the legacy arithmetic-only actual-CI field with the issued prediction. Decisions therefore cannot use actual future CI/PV to select a fallback. Only after controls are fixed does `score_fixed()` apply historical outcomes. Outcome failures are reported, not silently replaced. The old research path and benchmarks are preserved and retain their older retrospective limitations.

**Zero-PV capacity guard.** Every service optimization enables `robust_import_cap=True`. At each interval, fixed load + EV + batch + battery charge − discharge must fit the unchanged import cap with zero PV. Nonnegative PV may reduce imports or be curtailed. A fallback also must satisfy the same envelope before it is accepted. This protects against PV error with declared fixed load and working assets; it does not protect against arbitrary new base load, equipment outages or battery-model errors.

**Event replanning.** A request specifies simulation time, vehicle, revised total energy and deadline. EV power, battery charging/discharging and SoC before the event are fixed. Already-started batch jobs keep their start; unstarted jobs cannot be moved into the past. Events move strictly forward. A failed optimization cannot invoke the old immediate fallback and rewrite executed controls. All subsequent forecasts remain the original midnight forecasts; this is event-triggered optimization, not an online-learning or new-weather forecast claim.

**Actionable refusal.** Capacity diagnostics distinguish energy already delivered, an individual upper bound through the requested window, and an unavoidable shortfall lower bound. Shared constraints can make joint delivery worse. A rejected event can propose a later deadline after actually solving it with the same prefix. At most six deadlines are searched from the individual necessary bound; no proposal is not proof that every later time is impossible. The operator must explicitly use and replan that deadline. The software never silently relaxes the request.

**Disconnect assessment.** The UI calculates energy delivered at a selected time and the missing amount. A disconnected car cannot be repaired by reoptimization. This is an assessment of a simulated departure, not a hardware disconnect command or a persisted device event. No savings claim is allowed for that incomplete service assessment.

**Evidence.** Plan JSON, 48-row CSV, charts and generated evidence use the same `service-*` run identity. The identity covers the selected actions, not only the inputs. V2 evidence includes the service scenario and optional event history. The standard-library verifier reconstructs source lineage, physical limits and deadline energy, then checks parent dispatch digests, forward event order, request changes and unchanged executed prefixes. Forging zero actual CI and recalculating hashes still fails source correspondence.

## Experiment interpretation

The [protocol](../experiments/service_readiness/protocol.json) was written before executing the new scene outcomes. The original model, 0.7 carbon weight and 0.2 peak weight are retained. No test-best model or parameter is selected. The three-hour declaration is an operator requirement, not a tuned outcome parameter. The original 2025 training and validation chronology remains intact; the new implementation additionally checks all 60 complete July–August days using the then-available seasonal predictor. August 10–11 remain excluded for incomplete source outcomes, with reasons retained.

The repeatedly inspected 122-day September–December period is explicitly an **exploratory regression**, not a new independent time holdout. Four new, fixed synthetic configurations test a shared 11 kW station and 25 kW connection, four staggered vehicles, no battery, and no PV. These are new scenario tests on known grid/weather dates, not actual new sites or independent weather observations. The specifications were not adjusted after seeing which strategies won. The first full run was retained under `.runtime/service-readiness-first-pass`; the final rerun includes a reporting correction so rejected updates retain previously delivered energy, plus a decision-only fallback envelope check. Neither correction changes nominal strategy parameters.

Every simple strategy receives identical assets, efficiency, initial/terminal SoC, energy and early deadlines. Carbon/cost greedy and peak-shaving baselines can use the battery. Immediate deliberately leaves it idle and is labeled accordingly. Forecast ablation changes only the input prediction (frozen LightGBM, seasonal or latest). Simple-policy comparisons use the same protected service. Comparing the original all-day plan against the protected plan measures an additional service requirement, not superior optimization at equal service.

The [derived report](../experiments/service_readiness/REPORT.md), [raw rows](../experiments/service_readiness/daily_results.csv), [failures](../experiments/service_readiness/failures.csv), [paired comparisons](../experiments/service_readiness/paired_comparisons.json) and [machine audit](../experiments/service_readiness/audit.json) retain all attempts. Performance means exclude invalid schedules; use matched pairs rather than comparing means over different valid-day sets. In particular, immediate charging is infeasible in some of the tighter new sites, so no whole-period saving against it is claimed there.

The follow-up [recovery study](../experiments/service_readiness/recovery_summary.json) is explicitly exploratory after the same-deadline event failures were observed. It tests the actual product's proposal and acceptance path, assuming a manager can accept the later departure. A revised commitment is a service tradeoff, not a free improvement or independent validation.

## Results of the completed run

The final main run retained **6,160 policy/scenario/day rows**, took **305.81 seconds** on this workstation, and reproduced all original peak-aware nominal carbon, cost and peak values exactly across 122 days. All 60 complete validation days passed. Four new scene configurations each returned 122/122 physically valid protected plans; default daily workload is 62 kWh, four-vehicle workload 88 kWh, and no-storage workload 68 kWh. These are simulated stress/generalization results, not independently measured sites.

| Same three-hour early service, 122 days | Carbon kgCO₂/day | Illustrative £/day | Mean daily peak kW | Complete days |
|---|---:|---:|---:|---:|
| Immediate, battery idle | 34.945 | 61.703 | 34.053 | 122/122 |
| Greedy cost, same battery | 34.142 | **56.656** | 34.053 | 122/122 |
| Greedy carbon, same battery | **33.496** | 61.244 | 37.790 | 122/122 |
| Peak heuristic, same battery | 34.409 | 60.605 | 21.690 | 122/122 |
| Protected GridProof, frozen LightGBM | 33.759 | 57.425 | 18.983 | 122/122 |
| Same solver, seasonal forecast | 33.749 | 58.491 | 18.657 | 122/122 |
| Same solver, latest-value forecast | 34.435 | 59.086 | **17.341** | 122/122 |

Protected GridProof versus matched Immediate: **3.392% less carbon exposure, 6.932% less illustrative cost, 44.256% lower mean daily peak**. It has 13/122 worse-carbon days. Compared with greedy cost it pays £0.770/day for 0.383 kgCO₂/day less exposure and 15.070 kW less peak. Greedy carbon retains the lowest mean carbon among these methods. This is a tradeoff, not a universal win.

Original relaxed plan versus protected plan: carbon 33.491 → 33.759 kg/day; cost £56.785 → £57.425/day; peak 18.517 → 18.983 kW. Under unannounced departures three hours after arrival, the old plan completes 0/122 days and misses 27.533 kWh/day, whereas the protected plan completes 122/122. The difference comes from an advance service envelope; it does not mean predicting arbitrary departures.

Forecast contribution remains limited: LightGBM minus seasonal carbon is **+0.0106 kg/day**, paired seven-day block 95% interval **[-0.1297, +0.1511]**. Cost is **−£1.0655/day**, interval **[-£1.7192, −£0.4608]**. Carbon increment is unresolved. These intervals are exploratory, conditional on this simulated site and previously inspected time period, without multiple-comparison correction. The new protected solve's mean/p95 wall time was **0.101/0.368 seconds**; this is local per-policy timing, not public API latency or throughput.

Failures are material:

- Leaving after only two hours, outside the three-hour promise, still fails 122/122 days with **17.960 kWh/day** missing. Replanning after unplugging cannot fix that.
- At 08:00, adding 6 kWh to fleet-a while retaining its 10:00 deadline succeeds on **36/122** days. The other 86 requests are rejected and the prior controls are retained; each leaves 6 kWh of the revised request unmet. The mean shortfall across 122 attempts is 4.230 kWh, compared with 6 kWh if the old plan is always kept.
- In the separately labeled exploratory recovery study, the product proposes 10:30 for those 86 failures. **If the operator accepts that extra half-hour**, all 122 revised requests complete. No accepted extension is assumed by the main study.
- Zero actual PV with unchanged forecast preserves all 122 service/capacity successes; carbon improvement is 3.135% against matched immediate. Reversing actual CI timing also preserves service but reduces improvement to 1.501% and produces 36/122 worse-carbon days.
- Immediate fails the robust capacity requirement on all days in the shared-11kW/25kW-grid and no-solar/35kW-grid scenes. Its missing schedule is not treated as zero-emission success, and no aggregate saving against it is claimed there. Greedy carbon also fails some days; the raw attempts remain available.

## Data and trust boundaries

No new training or external dataset was added. The existing original NESO national CI and Open-Meteo ERA5 snapshots, licenses, retrieval metadata, original bytes and trusted hashes are reused unchanged; see [attribution](../ATTRIBUTION.md) and the [source anchors](../data/trust/source_anchors.v1.json). Decision transforms remain calendar PV, synthetic load and illustrative tariff. ERA5 irradiance is only a modeled outcome. Historical publication latency and revision availability are still assumed rather than archived. Missing complete source inputs cause an explicit rejection.

LightGBM is kept as a frozen cost/usefulness candidate, not an innovation trophy: the new protected-policy comparison still does not establish a carbon advantage over seasonal forecasting. No retraining is justified by these repeatedly inspected test results. Carbon is national-average location-based grid exposure. None of the results is measured campus abatement, marginal causal avoided emissions or a carbon credit.

A sustainability reviewer needs an independently recomputable report; signatures and a database are sufficient if everyone trusts one operator. A shared registry adds value when independent parties need a common commitment/replacement history. The current local EVM demonstrates that protocol but is not an independently operated or durable public registry. A hash does not authenticate a physical meter; self-contained parent hashes do not prove that the parent was published before the event. No chain or contract changes were necessary for this product improvement.

## Run and reproduce

```powershell
.venv/Scripts/python.exe scripts/run_demo.py
# http://127.0.0.1:3000 — new service workspace
# http://127.0.0.1:8000/docs — request schemas and API
.venv/Scripts/python.exe scripts/evaluate_readiness.py
.venv/Scripts/python.exe scripts/report_readiness.py
.venv/Scripts/python.exe scripts/evaluate_readiness_recovery.py
.venv/Scripts/python.exe -m pytest backend/tests scripts/tests -q
npm --prefix frontend run build
npm --prefix frontend run test:e2e
```

Run setup first on a fresh checkout. The experiment commands write only `experiments/service_readiness`; original benchmark outputs and model artifacts remain unchanged. Four shipped days operate without provider access. The evaluation reads the shipped separately pinned full original 2025 snapshots. Timing and generated evidence IDs may differ across runs; physical results and metrics should reproduce within stated tolerances.

## Honest competitive assessment

The strongest award case is now a concrete problem solved across product, optimization and verification: a manager sees a defensible ready-by promise, can challenge it with a real change, sees the exact limit when it cannot be met, and exports a report another person can inspect. That is stronger than a dashboard of favorable carbon percentages.

The largest unresolved weakness is external validity: no connected chargers, real load traces, continuous multi-day battery operation or observed human adoption. The fixed-load/device assumptions are still substantial. A top-three ambition is reasonable as an engineering target; neither these experiments nor known public competitors prove a ranking. Field evidence and a real operator's teach-back would be the next substantial improvement, not another model or page.
