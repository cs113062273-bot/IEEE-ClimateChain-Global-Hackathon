# GridProof: product-focused competition iteration

This iteration foregrounds a manager's decision: **choose an energy goal, inspect a feasible schedule, compare carbon/cost/peak, and challenge its evidence**. It improves the existing four-page application. It does not claim a winning probability or introduce a new model/benchmark result.

## Part A: direct answers

**Q1 — Hackathon versus research standards.** No inspected official rule requires LightGBM to significantly outperform Seasonal, p-values, bootstrap intervals or forecasting ablations. The actual five criteria concern climate impact, innovation, execution, usefulness and communication, without published numeric weights. Our trained forecast is genuinely used by forecast-based policies and feeds a separate constrained optimizer; the no-forecast and Immediate controls are labeled accordingly. Existing model comparisons remain in technical evidence. Repeating their limitation as the lead product conclusion gave a nonmandatory research question too much priority. [Official requirements audit](JUDGING_REQUIREMENTS_AUDIT.md).

**Q2 — Process.** The previous work repaired a real attack and exposed a real peak tradeoff. Its reports then overemphasized easily measured diagnostics relative to user decisions and external delivery. Three applied rules: start from a visible user decision and criterion; reuse sufficient evidence; validate the changed workflow and preserve failures with precise subjects. Account/publication authorization remains a real boundary, but the concrete release handoff is now prepared early. [Process correction](AGENT_PROCESS_RETROSPECTIVE.md).

**Q3 — Three likely losses.**

| Judge's attention | Concrete risk | Official criterion | Change and remaining acceptance |
| --- | --- | --- | --- |
| 30 seconds | Sees an engineering monitor without knowing whose decision improves | Presentation & Communication; Practical Usefulness | First viewport names the campus charging/peak problem, four goals and three same-workload deltas. Actual human teach-back remains pending. |
| Full 4:35 video | Thinks one policy is best on every axis, or hash matching proves meter truth | Climate Impact; Innovation & Creativity; Technical Execution | Show objective switching, the 122-day result separately from the selected day, one negative day, source-value forgery and four verification layers. Script now follows those exact actions. |
| Opens the app | Fixed-looking comparisons, exports disconnected from the chosen policy, cryptographic JSON before an explanation; no anonymous public entry | Practical Usefulness; Technical Execution; Presentation & Communication | Selected goal drives metrics, plots, dispatch, exports and generated evidence. Plain scope/history fields precede collapsed JSON. Render/static release is prepared; public Repo/video/hosting still require authorization/account actions. |

**Q4 — Value proposition.**

One sentence:

> GridProof helps campus energy managers choose feasible charging schedules that balance carbon, cost and peak demand, then independently check the evidence behind each decision.

100-word English description (whitespace-separated word count):

> GridProof is for campus energy managers who must charge vehicles, finish flexible work, and stay within electrical limits. Today, carbon charts and spreadsheets leave those decisions disconnected. GridProof forecasts grid intensity, solves feasible schedules, and compares carbon exposure, tariff cost, and peak demand under identical workloads. Managers can choose a goal, inspect the resulting schedule, export it, and challenge its evidence. Independent verification reconstructs inputs from pinned source snapshots. Blockchain adds an independently readable commitment and linked correction history outside the scheduling database. The prototype uses historical grid observations with simulated campus operations; it reports modeled outcomes, not field savings.

Approximately 20-second narration; actual delivery speed must be rehearsed:

> Campus managers need vehicles charged on time without creating a costly power peak. GridProof compares feasible schedules for carbon, cost and peak, then lets reviewers challenge their evidence. A separate blockchain commitment preserves the report's identity and correction history. These are simulated operational outcomes.

The blockchain contribution is shared report identity and correction history outside the scheduling database. It is not the only possible architecture: a signed transparency log can provide some similar properties. The current local chain does not provide public-network independence or certify upstream measurements.

**Q5 — Why Balanced is the default.** In the supplied comparison, Original Hybrid has lower carbon exposure than Peak-aware, while no-forecast peak control has lower peak. Balanced is useful because it improves all three reported means against Immediate and avoids the original hybrid's high peak. It is not universally optimal.

| 122-day policy | Mean exposure kgCO₂/day | Mean illustrative GBP/day | Mean daily peak kW |
| --- | ---: | ---: | ---: |
| Immediate | 34.945 | 61.703 | 34.053 |
| Original LightGBM hybrid | 32.884 | 58.420 | 48.227 |
| Peak-aware / Balanced | 33.491 | 56.785 | 18.517 |
| No-forecast peak control | 34.856 | 62.491 | 14.257 |

These are frozen full-period means, not the opening day's values. **Lowest Carbon → carbon_first, Lowest Cost → cost_first, Lowest Peak → peak_first, Balanced → peak_aware.** Labels describe objective preferences, not a guarantee of the lowest realized historical score. The original hybrid and Immediate remain selectable in the policy table/replay. Existing weight, battery and EV deadline controls trigger a real recomputation when Run optimization is clicked. Goal switching selects already computed policies; it does not fake a new solve or new AI forecast. The finite policy trade-off map highlights the current choice and reveals cost on hover; it is not the complete Pareto frontier.

**Q6 — Blockchain's present utility.** Removing the chain would retain source reconstruction, hashes, physics and database storage. It would remove the registry's separate commitment, exact-scope uniqueness and enforceable linked revocation/replacement records. Public network anchoring would further allow checks outside the application's operator; local Hardhat alone cannot supply that assurance. UI now shows site/period/category, actual record ID, previous/replacement links and revocation state before technical receipt JSON. Record IDs are not revision counters. New evidence can be deliberately submitted for a genuinely unregistered scope, read, modified and rejected; an already active scope is correctly rejected rather than silently reused. The recording uses a fixed report read to avoid duplicate-scope stalls. With no RPC, local source/physical checks remain usable and standalone offline replay works with no API/runtime; live-chain status remains unavailable/not checked. Sepolia is useful after source/video/public access, but not a hard submission gate in inspected rules. Prepare a fixed read-only proof, then deploy only after authorization; no additional contract functionality is warranted.

## Actually changed and why

| Work | User-visible outcome | Criterion | Engineering cost / scope |
| --- | --- | --- | --- |
| First-screen story and three-step path | Manager, decision and evidence purpose appear together | Presentation; Practical Usefulness | Low; existing pages and one shared component, no new runtime dependencies |
| Four objective buttons and consistent selection | Metrics, dispatch/SoC curves, replay, exports and generated report all use the chosen policy | Practical Usefulness; Technical Execution | Moderate UI integration; existing solver outputs, zero solver changes or parameter searches |
| Plain-language evidence challenge | Original CI value, rewritten zero value, new hash and rejected mappings are visible; technical JSON collapses | Innovation; Technical Execution; Presentation | Low; existing producer/verifiers/attack endpoint reused |
| Exact-subject receipt guard and lifecycle fields | Recorded receipt is enabled only for the fixed loaded report and checked against its digest; actual history fields are readable | Technical Execution; Presentation | Small UI/bridge change; no Solidity changes, no new RPC calls for history |
| Selected CSV/JSON export | 48 real intervals, units, scenario/policy, carbon/cost arithmetic and forecast-use labels are downloadable | Practical Usefulness | Low; browser download of computed values, no new backend endpoint |
| Release/facility-manager handoff | One Render profile plus static recorded fallback and explicit operator steps | Practical Usefulness; Presentation | Low configuration/docs; official schema validated, actual Docker/Linux/cloud not executed |

The two bounded adoption improvements are exports and facility-manager release operations. Existing limits remain available. Benchmark CSVs, model, source anchors and optimization code are unchanged. No new ML significance experiment was performed.

## Acceptance and records

- Product walkthrough: [60-second exact actions and human teach-back](ACCEPTANCE_60_SECONDS.md).
- Actual screens: [first viewport](assets/championship-first-view.png), [Control](assets/control-room.png), [Dispatch](assets/dispatch.png), [Replay](assets/replay.png), [Audit](assets/trust-audit.png), [phone](assets/control-phone.png), [forged source rejection](assets/lineage-rejected.png), [actual local receipt](assets/registry-verified.png).
- All six browser workflows ultimately pass across recorded runs. The integrated run had five passes and one failed selector: the text node also included a child subtitle. After correcting the selector and actual site/model-role labels, the final three affected workflows passed in 9.5 seconds: golden path, responsive pages and offline replay/export/attack. The three unchanged workflow tests had already passed in the integrated run. This is not a new final six-test run or a human comprehension measurement.
- The initial web restart used the repository instead of frontend working directory, so six connection tests failed before the correct server ran. Both startup and selector failure logs are retained. No test was removed. See [iteration validation](validation/championship-validation.json).
- Existing 32 contract/bridge tests and typecheck passed after actual lifecycle fields were exposed. Assertions were extended without increasing counts. [Observed release-preparation checks](validation/championship-release-preparation.json).
- Production build and frontend typecheck passed. Existing 91 Python/data tests and exact source clone remain evidence for the preceding unchanged engine/lineage release; they were not relabeled as a new full clone or rerun merely to increase counts.
- Offline recorded selection/export/source-forgery workflow passed with browser networking disabled. Actual local-chain read verified the fixed release report; no public chain transaction occurred.
- Human 60-second comprehension, public links, actual video and authenticated form acceptance are **pending**, not passed by E2E.

Visual review corrected two actual presentation errors before release: a claim scope stores a site hash, so the displayed site name now comes from the declared scenario; Cost-first and zero-carbon-weight hybrid policies do not use the carbon prediction in their objective. Their flow/export labels now say so. Immediate is labeled as the actual earliest-job heuristic, not MILP. The carbon prediction genuinely guides Carbon-first and positive-carbon-weight Hybrid/Balanced decisions.

Read verification now clears its prior success while checking and becomes UNVERIFIABLE/INCOMPLETE on failure; the browser test verifies this after a genuine successful local read.

A final screenshot navigation also encountered a real transient proxy `ECONNRESET` on GET `/api/scenarios`. A subsequent probe succeeded; the underlying cause is unresolved. The client now retries an idempotent GET once after 200 ms on a network error or HTTP 5xx. POST operations, validation failures and explicit chain states are not retried; persistent failures still show the real error and offline fallback. The responsive workflow injects one transport 503 then reads the real server response. [Observed incident](validation/championship-navigation-incident.json) preserves the failure; this is an existing reliability fix, not a new adoption feature or an assertion of cloud readiness.

## Release and remaining human steps

[Release operations](RELEASE_OPERATIONS.md) prepares the existing app and static fallback; [render.yaml](../render.yaml) has no deployed resources. Anonymous repository access still returns 404. Public GitHub, service deployment, video upload and Devpost submission remain separately authorized account steps. The official deadline conflict is UNRESOLVED; plan against October 25, 2026 at 22:00 Asia/Taipei and ask the organizer using the unsent draft. Taiwan-specific eligibility and the actual form/35 MB requirement must be checked by the entrant. No public deployment, upload, push or submission was performed.

The strongest distinction versus CarbonShield is **executable constrained energy decisions plus independently challengeable evidence**, not hashing or anchoring alone. The largest remaining competitive weakness is external delivery and real-user/field adoption evidence. [Short primary-source comparison](COMPETITOR_COMPARISON.md).
