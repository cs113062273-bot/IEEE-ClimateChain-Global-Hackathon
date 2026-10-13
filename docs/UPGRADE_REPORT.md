# GridProof competition upgrade

The source-lineage weakness is repaired, all 122 held-out days are evaluated, peak-aware dispatch is measured, and the judge demo has trained-model and independent attack workflows. Public delivery still requires the entrant's account actions and authorization.

## Before and after

| Area | Prior state | Current implementation and evidence |
| --- | --- | --- |
| Source proof | Internally consistent zero-CI rewritten report could pass after rehashing | Independent raw-source/model reconstruction rejects it even while integrity and physical arithmetic pass |
| Missing source | Missing original files could be warnings with a green result | Required original bytes/model/external pins must be available; otherwise INCOMPLETE; optional local copies explicitly NOT_LOCALLY_CHECKED |
| Legacy proof | v1 appeared fully verified | v1 preserved and readable as INTEGRITY_ONLY / LEGACY_UNVERIFIED |
| Prediction demo | January/August seasonal only; untracked pickle required for ML | Four dates include September 1 and October 13 using distributed portable original trained trees |
| Peak | Carbon-cost hybrid increased peak | Optional epigraph objective and zero-PV guard; optional hard cap; no-forecast peak control |
| Evaluation | 24 sampled days | 122 consecutive days, 17 policies, 12 fixed weight settings, 16 sensitivity cases, paired AI comparison and block bootstrap |
| Judge UI | Four working pages | First-screen peak, model/error visibility, Carbon/Cost/Peak comparison, four verification layers, forged-and-rehashed failure, separate existing-scope read |
| Offline backup | JSON/screenshots plus local runtime | Self-contained HTML recorded replay; no Python/Node/API/wallet/network required |
| Public chain | Local-only bridge | Sepolia fixed-proof/read-only lookup and safe operator preparation implemented; public deployment pending |

## Measured result

On the same 122 simulated daily scenarios:

| Policy | Mean kgCO2/day | Mean illustrative GBP/day | Mean daily peak kW | Aggregate exposure improvement | Non-improving days |
| --- | ---: | ---: | ---: | ---: | ---: |
| Immediate | 34.945 | 61.703 | 34.053 | 0% | Reference |
| Original LightGBM hybrid | 32.884 | 58.420 | 48.227 | 5.897% | 7 |
| Peak-aware LightGBM hybrid | 33.491 | 56.785 | 18.517 | 4.162% | 4 |

Peak-aware reduces the mean peak 45.624% and illustrative cost 7.970% relative to Immediate, while giving up some of the original hybrid's carbon improvement. Its mean daily exposure improvement is 4.302%, distinct from aggregate 4.162%. October 13 still slightly worsens carbon. The original 24-day files and all 120 carbon/cost outputs remain unchanged.

The LightGBM/seasonal paired improvement confidence intervals include zero. Custom AI has not established a reliable incremental advantage. Forecast complexity is not the core climate claim.

Execution: 926.939 seconds wall, 995.984 CPU seconds, 10,062 native MILP calls, whole-process peak working set 358.699 MiB. Maximum measured call is 1.753096 seconds; retained maximum gap is 3.3144e-6, above the requested 1e-6 on 48 rows. This is actual measured behavior, not a promise that the requested tolerance is always attained.

See [complete tables](COMPETITION_EVALUATION.md), [consistency audit](BENCHMARK_CONSISTENCY.md), [raw data](../experiments/competition_v2/daily_results.csv) and [plots](../experiments/competition_v2/figures/).

## Delivery

- [README and local start](../README.md), [offline browser demo](../offline/index.html).
- [Source-lineage technical report](LINEAGE_VERIFICATION.md), trusted upstream pins under `data/trust/`.
- [4:35 storyboard, narration and operations](DEMO_SCRIPT.md), [Devpost English text](SUBMISSION_DESCRIPTION.md).
- [Minimal human steps](SUBMISSION_CHECKLIST.md), [public hosting/Sepolia preparation](PUBLIC_DEPLOYMENT.md).
- [Actual tests and retained failures](VALIDATION.md).

## Remaining risks and subjective assessment

The source snapshot trust root must itself come from a trusted release or independent provider check. This system does not prove provider truth, historical publication availability, optimality, actual campus deployment or causal avoided emissions. The test covers September through December of one year and one declared site template. Sensitivity fallbacks show where forecast planning can fail during realized replay. Docker/Linux/cloud execution and public service reliability are unverified.

Review scores out of ten, without invented official weights: Climate Impact **6.5**, Innovation **7.0**, Technical Execution **8.5**, Practical Usefulness **6.5**, Presentation **7.5**. These are a subjective technical assessment, not organizer scores or winning probabilities. Field evidence and public/video delivery remain the largest deductions.

The repository was still anonymously unreadable at the verified check. Actual video recording/upload, personal eligibility and logged-in submission form, public repository/hosting/testnet authorization and final submission are not completed by local implementation.
