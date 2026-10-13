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
