# Execution worklog

## 2026-10-13 — Start

Read root IMPLEMENTATION.md and CODEX_START_PROMPT.md. Original starter assets retained. Workspace initially contained the specification, prompts, architecture drawings and starter archive, with no application source or datasets.

Verified installed Python 3.11.9, Node 24.19.0, npm 11.17.0, Git 2.53.0.windows.2. `py -0p` failed because the Windows Python launcher is not installed; use `python` and `.venv/Scripts/python.exe`.

Parallel workstreams: official data/source acquisition; constrained backend and chronological evaluation; Solidity local registry. Dashboard uses Next.js, TypeScript, Tailwind and Recharts with pinned dependencies. No external publication or paid resources authorized.

Commands and source checks are preserved in DATA_WORKLOG.md, CHAIN_WORKLOG.md and the backend evaluation report. Gate results will be appended after actual verification, without promoting incomplete features to passed status.

## Final verified gates — 2026-10-13

| Gate | Actual result | Evidence and run command |
| --- | --- | --- |
| G0 | Passed core acquisition/QC. 2025 CI and demand each 17,520 rows; 2026 CI 13,690; weather 8,784 hours including padding; PVGIS 2023 8,760 model records. UKPN consumption is restricted, not downloaded. | `python scripts/validate_sources.py --require-bulk`; DATA_CATALOG.md and source manifest contain real byte counts, SHA256 and missingness. Five typed Parquet tables plus DuckDB stored locally. |
| G1 | Passed numerical optimization, strict inputs, API and failure handling. | `.venv/Scripts/python.exe -m pytest backend/tests scripts/tests -q`: **49 passed**, comprising 41 backend and 8 data tests. `pip check`: no broken requirements. |
| G2 | Passed actual local-chain lifecycle and independent verification. | Hardhat build/typecheck and **19 contract/bridge tests passed**. Final September 12 commitment at block 9; chain worklog records actual immutable history, tamper mismatch, duplicate rejection and wrong-chain failure. |
| G3 | Passed reproducible chronological evaluation, with explicit failures. | 24 held-out scheduling days; hybrid mean exposure difference 7.358321%, one non-improvement, zero constraint violations. LightGBM fails latest-known test MAE. Actual CSV/JSON reports in experiments/, details in EVALUATION.md. |
| G4 | Passed four-page app build and browser workflows. | `npm --prefix frontend run build`, `run typecheck`, `run test:e2e`: **3 browser tests passed**. Tested computed schedules, deadline rejection, replay, independent browser SHA256/tamper, responsive width and deliberate local attestation/duplicate rejection. Screenshots inspected at 1366×768 and 1920×1080; mobile overflow checked at 390×844. |
| G5 preparation | Local install/dependency pins, launch scripts, README, source attribution, threat model, measured reports and presentation assets prepared. | Two-day isolated source-copy replay passed with bulk data/model absent and external network denied, using already installed dependencies. Public repo/video/hosting are not published. Fresh Git-clone smoke result follows below. |
| G6 | Pending entrant eligibility review, recording/upload and explicit publication/submission instructions. | SUBMISSION_CHECKLIST.md retains unresolved official rule contradictions. No contest submission performed. |

The initial Windows solver ran successfully for simple tests but a repeated FastAPI replay test triggered a native access violation. The final implementation serializes HiGHS calls through one persistent worker and fixes native threads to one. Repeated/concurrent request tests passed after the change; all 24-day policy outputs remained the same. This is a tested local mitigation, not an assertion that an upstream bug was fixed.

Independent review also corrected nonfinite rehashed evidence claims, canonical numeric overflow, ambiguous forecast issue timestamps, multi-day replay ID collisions, silent multi-day evidence selection and use of validation-based model selection before September 1. Final source/weights hashes are captured in the evidence. Historical actual publication latency remains unarchived and is disclosed as an availability assumption.

The first browser rerun encountered Next.js's separate route-announcer alert; the test selector was narrowed to the application error. The UI chain test initially expected `VERIFIED` directly after a write; the implementation correctly returned `ATTESTED`, requiring a separate read verification. The expectation was corrected, and the independently checked real January 15 UI transaction is `0x4abb6b0773fe9f9b024f4f0942b90ef570e0dd650d0c9f1a5a583968e138a683`, block 7. GET `/api/verify/0xdfefee7aa5596c0e6f6530321f05141a2300d979f78e53810c2e77b47122dbe3` returned `VERIFIED`. August 12 remains available for a new local attestation in this chain.

Source manifests are read-only during routine QA. Rebuilding them requires explicit `--write-manifest`. Fresh copies show unavailable bulk snapshots rather than claiming those files exist. The eight source tests passed after adding explicit local-asset availability to terminal audits.

The final UI review corrected replay request parameters: edited battery/job/objective settings are now sent with the original computed comparison rather than reverting to defaults. Browser assertions compare the replay run ID, selected 60-kWh battery and outcome metrics to the original run. Cached objective controls also restore the previously computed weight.

Setup commands installed the pinned Python, frontend and contract dependencies on this Windows host. Unix scripts are supplied but not executed on a Unix host. The isolated source-copy test validates offline behavior with the installed dependency environment; it does not claim a separate clean dependency installation.

Local preview: http://127.0.0.1:3000; API docs: http://127.0.0.1:8000/docs. `scripts/run_demo.ps1` / `sh scripts/run_demo.sh` launches/reuses the local pieces. Runtime logs, databases, local chain metadata, raw data and model binaries are ignored. No paid resources, public source push, hosted deployment, video upload or submission was performed.

## Fresh Git-clone check

Created a local source commit and cloned it to `.runtime/fresh-clone-f5e27d1`. The clone contained no downloaded bulk files, trained model or runtime chain metadata. Using the installed Python environment, `scripts/smoke_test.py`, the standalone verifier on the shipped evidence and sample source validation all passed. Missing upstream bulk snapshots produced explicit warnings/local availability labels. The fixture SHA256 stayed `134251a6f846bd492b2208041cd6615ad892678dc8e94b4be9a6fa5cc8e3d8d5` after Git checkout.

Executed `npm ci --offline --no-audit --no-fund` independently in the clone's frontend and contracts: both installed successfully from the npm cache with no network. The clone's Next.js production build/type check and Solidity build both passed. This checks fresh node dependency installation and source packaging, while Python uses the already installed pinned environment. `.gitattributes` preserves exact bytes rather than converting line endings that would invalidate evidence fingerprints.

Final browser suite passed all three workflows after parameter replay and normalized-default identity fixes. Equivalent compare/replay requests now produce the same run ID and metrics. Final backend suite has 41 tests, source suite 8, contract/bridge suite 19 and browser suite 3.

## Competition-strengthening release, 2026-10-13

The sections above describe the original release and its historical local chain. The upgraded implementation was committed as `e7cd586bef91e9da379a86bc87b350f32b16c66a`, followed by final recorded-proof UI and validation artifacts at `a29daadc79af054a4eeb33dddc86e6b74e24b74a`. Original Git history, v1 report and 24-day benchmark values are preserved. The user's independent `review.md` remains untouched and outside these commits.

Source-lineage v2 independently reconstructs original CI, past-only forecasts and trained trees, PV, declared simulated loads/tariff and Immediate reference against separate source pins. Fully rehashed zero-CI forgery now fails Source Lineage while Integrity and Physical Validity pass. Missing necessary source/anchor/model material is INCOMPLETE; v1 is INTEGRITY_ONLY. No meter truth or environmental certification is claimed.

The measured complete period is September 1 through December 31, 2025: 122 consecutive UTC days, 17 policies, 12 weight settings and 16 sensitivity cases. Peak-aware total modeled exposure improvement is 4.1615%, mean daily improvement 4.3024%, reduction of mean peaks 45.6241% and illustrative cost reduction 7.9701%; four negative days are visible. LightGBM-versus-seasonal paired intervals include zero. The run took 926.939 seconds and 358.699 MiB peak working set. Sensitivity failures, 195 rejected candidates/fallbacks and 48 gap overruns remain disclosed. See [full evaluation](COMPETITION_EVALUATION.md) and [independent consistency review](BENCHMARK_CONSISTENCY.md).

Final original-checkout tests: 91 Python/data, 32 contract/bridge and 6 Edge E2E passed; production build/typechecks/source audit passed. A fresh local Git clone of exact commit `a29daadc79af054a4eeb33dddc86e6b74e24b74a` had no ignored bulk data, pickle, runtime or node_modules. Its newly installed pinned Python environment passed all 91 tests and independently verified the shipped report; all four dates/seven policies worked. Both npm packages installed offline from cache, and frontend/contract builds plus typechecks passed. The mistaken first `data/tests` invocation ran no tests; its failed log remains alongside corrected `scripts/tests` results. [Actual validation records](VALIDATION.md) describe scope and failures.

User interruptions stopped local services. Prior chain deployment metadata and receipts were archived rather than reused as current verification. Final startup created a fresh local registry, then deliberately registered the same fixed September 1 v2 report at block 2 and read its real receipt, followed by duplicate rejection. [Final preview capture](validation/local-preview-attestation.json) records these actual loopback-only actions. API/dashboard/node were healthy at capture. Startup never auto-attests.

The four-page dashboard, standalone offline HTML, 4:35 storyboard/verbatim narration, English Devpost text, Docker/readonly Sepolia preparation and minimal human submission checklist are delivered. Linux/Docker/cloud, actual video, anonymous repository publication, personal eligibility/account fields and formal Devpost submission remain pending. No public push, visibility change, hosting, Sepolia deployment, public transaction or contest submission was performed.


## 2026-10-19 — Service-first GridProof

Preserved the user's pending competitiveness audit, optional import guard, original benchmark and model artifacts. Inspected source, raw outcomes, official scoring criteria and mature ready-by/adaptive scheduling references, then operated the old UI before changing it. Main product is now the protected-departure workspace; old pages are retained under the research navigation.

Added full-energy earliest-departure constraints, future-outcome isolation, mandatory zero-PV cap protection, fixed executed controls/SoC in event replanning, quantified refusal and separately solved later-deadline proposals, disconnect shortfall assessment, matched battery-equipped baselines and independent event-history verification. Implemented and visually checked desktop/mobile workflow with exports tied to the selected service run. No model retraining, external publication, account action or formal contest work.

Completed 104 Python/data checks, 32 contract/bridge checks, optimized frontend build/typecheck and 8 production-browser workflows. Main experiment: 6,160 rows, 305.813 s; original 122-day results exactly reproduced. Protected early service improves from 0/122 old interrupted plans to 122/122, with an explicit +£0.640/day and +0.269 kgCO₂/day cost relative to relaxed service. Against same-service Immediate: −3.392% carbon exposure, −6.932% illustrative cost, −44.256% mean daily peak. Four new fixed synthetic sites complete 488/488 site-days. Subsequent recovery study preserves 86 same-deadline failures and shows completion only after explicit acceptance of a 30-minute extension. Full boundaries, negative results and commands: [READINESS_ENGINEERING.md](READINESS_ENGINEERING.md).


## 2026-10-19 — Workplace car-park controller on real sessions

Verified the inherited state: 104 Python tests passed; the readiness study's 122/122 completion is deterministic (no feasibility input varies by day); LightGBM carbon forecasting has no resolved carbon value. Chose a new core: departure-risk-aware charging for a workplace car park on a capped connection.

Downloaded the 4TU Utrecht office car-park sessions (CC BY-NC-SA 4.0, no account; kept out of git). Built UTC session normalisation, leakage-free per-driver history features, an 8-level LightGBM quantile departure model with conformal calibration, an online controller (earliest-promise-first, least-laxity, equal share, an expected-shortfall LP), operator events, an exact shortfall bound, an evidence record with a standard-library verifier including decision replay and session lineage, API routes, and a new main UI.

Wrote the protocol before any 2024 simulation, selected on 2023 H2 and tested once on 185 held-out days. Fixed during development, all before the test: a whole-slot presence inconsistency, quantile rearrangement order, a coverage-print broadcast bug, missing lower-tail risk mass. Found on the test and reported rather than tuned: LP myopia at tight caps, a suboptimal tie-break. Corrected a mis-built sensitivity case (unknown requests) and a wrong hand calculation in a test. Restored line endings of files changed by a bulk rewrite and re-ran the frozen pipeline; results identical.


## 2026-10-19 — Review follow-ups

External review reproduced a 34-to-1 session-omission forgery that passed all four record layers; source correspondence now checks completeness in both directions, with a third built-in forgery and a regression test. Overclaiming copy replaced ("requests met in full"). Old fleet and research pages unlinked and bannered as archives. A second review asked for decision-time inputs and simple personal-history baselines: under decision-time inputs the gain over equal share halves but stays significant at 100-150 kW (slightly negative at 80 kW); a simple personal quantile is statistically indistinguishable from LightGBM at 120-150 kW. The product switched to decision-time inputs, carbon-flex is labelled experimental and not recommended, and the docs claim personal history rather than LightGBM.
