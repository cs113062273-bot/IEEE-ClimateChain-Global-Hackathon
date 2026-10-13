# GridProof — Feasible energy schedules, independently checkable evidence

**Primary track: Renewable Energy & Energy Trading — Microgrid Coordination.** The English description below is ready to copy into Devpost. Publication links remain a manual handoff: a script is not a recorded video, and deployment preparation is not a published service.

## Problem and users

A campus energy manager must charge a fleet before departure, finish flexible work and stay within electrical limits. A carbon-intensity chart alone does not produce that schedule. Moving everything into a low-carbon period can also create an expensive power peak. The operator then needs a report another person can challenge without trusting a dashboard screenshot.

GridProof turns these requirements into a feasible plan and independently inspectable evidence. It serves campus, fleet and small industrial operators. Authentic historical national Great Britain carbon-intensity records underpin a hypothetical London campus with 20 kWp rooftop PV, a 40 kWh battery, two EV jobs and one contiguous lab workload. Campus demand, devices and tariff are simulated. Weather is historical reanalysis and rooftop production is modeled; this is not a connected field trial.

## Working solution

The SciPy/HiGHS mixed-integer optimizer enforces half-hourly energy balance, battery efficiency and state-of-charge bounds, equal starting and ending stored energy, vehicle demand/deadlines, shared charging power and contiguous work. Peak-aware scheduling adds a maximum-power objective or cap with an explicit conservative zero-PV guard. Carbon, cost and peak are tradeoffs.

The four-page interface starts with a campus operator's decision: **Lowest Carbon, Lowest Cost, Lowest Peak or Balanced**. Selection updates the same-workload metrics, power and battery curves, interval replay, 48-row CSV/JSON export and generated evidence. Goal switching displays actual computed policies; changing battery capacity, EV deadline or hybrid preference sends a real recomputation. Goal names describe objectives, not guaranteed realized minima.

LightGBM uses past carbon observations and calendar features. Its carbon forecast guides Carbon-first and positive-carbon-weight Hybrid/Balanced objectives. Cost-first uses tariff and calendar PV instead; Lowest Peak and Immediate do not use carbon predictions for decisions. The UI and exports state these roles. Dates before model selection use a labeled seasonal fallback. Future actual intensity is used for retrospective scoring, never as an ordinary decision feature.

## Measured prototype results

We evaluated **all 122 consecutive UTC days from September 1 through December 31, 2025**, with identical demand and assets for each paired comparison. Modeled location-based grid-emissions exposure is imported energy multiplied by historical actual national carbon intensity. The tariff is illustrative and replayed PV is radiation-derived simulation.

| Policy | Total exposure kgCO₂ | Total improvement | Mean daily improvement | Mean cost £/day | Mean daily peak kW | Carbon-worsening days |
|---|---:|---:|---:|---:|---:|---:|
| Immediate, battery idle | 4,263.275 | 0% | 0% | 61.703 | 34.053 | 0/122 |
| Original LightGBM carbon–cost hybrid | 4,011.886 | 5.897% | 6.365% | 58.420 | 48.227 | 7/122 |
| Peak-aware LightGBM hybrid | 4,085.857 | **4.162%** | **4.302%** | **56.785** | **18.517** | **4/122** |

Relative to Immediate, the peak-aware policy lowers the mean daily peak by **45.62%** and mean illustrative cost by **7.97%**, sacrificing some carbon benefit compared with the original hybrid. These are ratios of reported means. Mean per-day peak reduction is a different statistic, **45.56%**. The total-exposure reduction has an IID day-bootstrap 95% interval of **[3.710%, 4.613%]**; mean daily improvement has a seven-day block-bootstrap interval of **[3.764%, 4.913%]**. Four carbon-worsening days remain visible. All 122 nominal peak-aware comparisons have valid constraints, no fallback and no failed day; maximum measured solve time was approximately 0.54 seconds on this development machine.

We retain persistence, seasonal, perfect-carbon-information and objective-independent controls, sensitivity cases, negative outcomes and solver diagnostics. Paired LightGBM-versus-seasonal confidence intervals include zero: **custom AI has not demonstrated a reliable carbon advantage over the strong simple baseline**. Training, validation and test windows are chronological. This follow-up design was made after the earlier audit; it is not an untouched or preregistered test. It covers one autumn/winter period, not four seasons.

The frozen configuration and results are in `experiments/competition_v2/`: daily CSV, three-objective tradeoff grid, sensitivities, paired intervals and an independent numerical consistency audit. Larger peaks, infeasible inputs and non-improvements are retained.

## What evidence and blockchain establish

Version 2 evidence includes inputs, pinned upstream bytes, portable trained-model representation, transformations, operational settings, dispatch and fingerprints. An independent standard-library Python verifier reconstructs CI, forecasts, weather-to-PV conversion, synthetic load and tariff, then checks physical constraints and arithmetic. Trusted source anchors come from a separately reviewed release, not self-certified report hashes. A counterfeit that changes CI to zero and rehashes the report now fails source-lineage verification even when its new SHA256 matches.

The interface separates **Integrity**, **Source Lineage**, **Physical Validity** and **On-chain Attestation**. Missing necessary sources produce incomplete assurance. Older v1 reports retain their bytes and integrity checks but cannot silently acquire v2 source assurance.

The Solidity registry commits a digest outside the scheduling database and enforces one active claim for an exact site, time interval and category. Authorized revocation/replacement preserves linked history, shown as actual fields before technical JSON. Real local EVM receipts have been exercised. Fixed-proof reading is separated from dynamically generated reports so a new digest cannot borrow an old attestation. Anonymous Sepolia read-only verification is prepared, but public deployment and a fixed published proof remain pending authorization. A hash, valid lineage or registry commitment does **not** prove that an external meter or provider told the truth, establish site ownership or certify a carbon credit.

## Adoption and limits

A facility manager can inspect constraints, compare goals and export the selected plan for review. The export is a planning artifact, not a command to connected chargers. The release provides existing-app hosting configuration, a static fallback and operator instructions. Adoption proceeds from transparent replay to validated meters and point-in-time data, followed by operational trials and measured field evaluation. Current support is one 24-hour horizon with bounded jobs; daily battery states reset. Multi-site coordination, long continuous horizons and large fleets require further engineering.

A self-contained `offline/index.html` lets a judge inspect recorded comparisons, replay flows and challenge evidence without Python, Node or a wallet. Its lightweight browser checks are labeled separately from complete Python verification; it performs no new optimization or live chain query. Hosting/container settings are prepared but have not been validated in Docker or a Linux deployment.

GridProof contributes a physically feasible plan, an honest carbon–cost–peak comparison and evidence a reviewer can independently reconstruct and attack. It reports modeled exposure, not causal avoided emissions or field-validated savings.

## Publication links — replace only with verified deliverables

- Source candidate: `https://github.com/cs113062273-bot/IEEE-ClimateChain-Global-Hackathon`. Anonymous webpage/API returned 404 on October 13; public readability is **not yet confirmed**.
- Demo video: **not recorded/uploaded**. Use the [4:35 storyboard and narration](DEMO_SCRIPT.md).
- Hosted prototype: **not published**. Local and self-contained offline demos are prepared.
- Public-chain proof: **not deployed or registered**. Insert an explorer link only after an authorized transaction verifies.
- Account steps and submission confirmation: [submission checklist](SUBMISSION_CHECKLIST.md).

The archived 24-day 7.36% daily-mean headline is historical context, not the current full-period result.
