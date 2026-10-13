# GridProof

**Trustworthy carbon-aware microgrid orchestration** — a working local prototype for the IEEE ClimateChain Global Hackathon 2026, Renewable Energy & Energy Trading track.

GridProof turns authentic GB grid records into constrained campus energy schedules and independently verifiable evidence. It connects source acquisition, forecasts, a mixed-integer optimizer, numerical replay and a Solidity scope registry. The hypothetical London campus has 20 kWp PV, a 40 kWh battery, two EV jobs and a contiguous compute-lab batch.

![Computed campus control room](docs/assets/control-room.png)

## Run the local demo

Prerequisites: **Python 3.11** and **Node 24**. All application dependencies are pinned in requirements.txt and npm lockfiles. Setup downloads dependencies; after installation the attributed two-day sample runs without provider Internet access.

```powershell
# Windows, from the repository root
.\scripts\setup.ps1
.\scripts\run_demo.ps1
```

```sh
# macOS / Linux
sh scripts/setup.sh
sh scripts/run_demo.sh
```

Open **http://127.0.0.1:3000**. FastAPI docs: http://127.0.0.1:8000/docs. The zero-cost local EVM is at 127.0.0.1:8545, chain 31337. The startup command deploys or reuses a local registry; it does not attest evidence automatically. Stop the command with Ctrl+C to stop the API/dashboard processes it started. The independently managed local chain can be reused for later demonstrations.

PowerShell users with script execution restricted can invoke `.\.venv\Scripts\python.exe scripts/run_demo.py` after setup, or run the setup commands directly. No Python `py` launcher is required. The local demo uses cached official records, transparently simulated site data and an illustrative tariff. A fresh source copy uses a past-only seasonal forecast; full-data training adds the validation-selected model for eligible later decision dates.

## Four working pages

- **Control room:** numerical campus twin, carbon outlook, modeled exposure and independent constraint checks.
- **Intelligent dispatch:** choose a source day, battery capacity, EV deadline and cost/carbon weight; recompute all policies. Infeasible inputs return an explicit error.
- **Digital twin & replay:** inspect each half-hour, compare equal-workload policies, reproduce a day and export the dispatch. Held-out evaluation is shown separately from the selected-day outcome.
- **Trust audit:** export evidence, independently recompute SHA256 in the browser, tamper with a copy, deliberately attest on the local chain and verify its receipt. Missing RPC or mismatched evidence never becomes a verified state.

## Measured results and limits

The locked scheduling benchmark used **24 preselected days from September–December 2025**, identical workloads and physical limits, and zero reported constraint violations. The hybrid policy averaged **7.36% lower modeled location-based grid-emissions exposure** than immediate charging; the 95% day-bootstrap interval was **5.42–9.42%**. It failed to improve exposure on one of those days. Carbon-first failed to improve on six days. Costs are hypothetical tariff calculations.

Forecasting trained chronologically on January–June, selected a model on July–August validation, then evaluated September–December without test-period selection. LightGBM test MAE was **36.98 gCO₂/kWh**, compared with **34.84** for the latest-known-value baseline and **47.06** for the seven-day seasonal median. The custom model therefore failed to beat the strongest simple baseline on test MAE. NESO's historical forecast had **9.23** test MAE, reported as a secondary comparison with unverified historical issuance provenance.

The full 2025 national CI snapshot has **17,520 half-hour rows**, including **43 missing actual values**, retained as null. Downloaded data include 2025 demand, 2025 London ERA5 weather with end-of-year padding, 2026 CI through the retrieval cutoff, and a supported **2023** PVGIS production model. UKPN consumption records returned HTTP 403 and are not used. Raw files, byte counts, exact URLs, units, retrieval times and SHA256 fingerprints are documented in the [data catalog](docs/DATA_CATALOG.md) and source manifest.

These are modeled operational outcomes, not measured facility deployment, causal physical avoided emissions or carbon credits. Grid intensity is national average, not marginal London intensity. Rooftop production, fixed demand, device operation and jobs are simulated. Weather reanalysis enters outcome replay, while decision PV uses a disclosed calendar forecast. Blockchain commits to report integrity; it does not establish meter truth. See [evaluation](docs/EVALUATION.md), [assumptions](docs/ASSUMPTIONS.md) and [claims and limits](docs/CLAIMS_AND_LIMITS.md).

## Reproduce full-data acquisition and experiments

```powershell
.\.venv\Scripts\python.exe scripts/discover_sources.py
.\.venv\Scripts\python.exe scripts/fetch_neso.py --year 2025
.\.venv\Scripts\python.exe scripts/fetch_neso.py --year 2026 --ci-only --through 2026-10-13
.\.venv\Scripts\python.exe scripts/fetch_openmeteo.py
.\.venv\Scripts\python.exe scripts/fetch_pvgis.py --year 2023
.\.venv\Scripts\python.exe scripts/build_snapshot.py
.\.venv\Scripts\python.exe scripts/profile_sources.py
.\.venv\Scripts\python.exe scripts/validate_sources.py --require-bulk --write-manifest
.\.venv\Scripts\python.exe scripts/train_models.py
.\.venv\Scripts\python.exe scripts/run_benchmark.py --days 24
.\.venv\Scripts\python.exe scripts/make_demo_fixture.py
.\.venv\Scripts\python.exe scripts/smoke_test.py
```

On Unix replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`. `scripts/setup.ps1 -DownloadData` or `sh scripts/setup.sh --download-data` prepares the core 2025 datasets. 2026 and UKPN are optional separate commands. Acquisition caches responses, verifies checksums, implements bounded retry/backoff and timeouts, and records failures rather than inventing successful downloads. Diagnostic plotting, Parquet and DuckDB conversion operate on the cached normalized records.

The source audit is read-only unless `--write-manifest` is explicitly requested. `validate_sources.py` validates the shared fixture on a fresh clone; `--require-bulk` also requires all downloaded artifacts. A missing full dataset is visible, never silently reported as present. Retraining and re-evaluation require the full download, while the two-day demo requires only the sample.

## Verify evidence independently

Export JSON from Trust audit. The standalone verifier imports no backend modules and recomputes the canonical digest, energy balance, battery dynamics, job constraints, scope and results:

```powershell
.\.venv\Scripts\python.exe scripts/verify_evidence.py evidence.json --digest 0xYOUR_EXPECTED_SHA256
```

Use the original trusted digest or on-chain commitment, not a newly computed digest supplied with an untrusted edited report. Missing bulk source files produce explicit warnings; available local source and code fingerprints must match. The canonical format is `gridproof-canonical-json-v1`: ASCII keys sorted recursively, compact UTF-8 JSON, finite floating values normalized to nine-decimal strings, safe integers preserved. It is explicitly not an RFC 8785 implementation.

The registry uniqueness key contains only `(siteHash, fromUtc, toUtc, categoryHash)`. Model/scenario labels cannot create a duplicate active scope. An original submitter can revoke and explicitly replace, with immutable linked history. The protocol does not establish site ownership, globally detect overlapping intervals or certify emissions. [Contract threat model](docs/THREAT_MODEL.md) · [actual local chain receipts](docs/CHAIN_DEMO.md).

## Tests

```powershell
.\scripts\check.ps1
# With the local demo running; Windows uses installed Microsoft Edge:
npm --prefix frontend run test:e2e
```

```sh
sh scripts/check.sh
# Install Chromium for Playwright once on Linux/macOS:
cd frontend
npx playwright install chromium
npm run test:e2e
```

Tests exercise DST settlement conversion, source integrity and missingness, no future feature/weather leakage, feasible and infeasible deadlines, energy conservation, terminal SoC, battery exclusivity, shared charger caps, batch contiguity, solver failure/time limits, canonical tampering, independently reconstructed arithmetic, duplicate registry scopes, authorization, replacement history, wrong-chain/RPC handling and the browser workflow. [Execution worklog](docs/WORKLOG.md) records actual pass counts and verification limits.

The verified Windows run passed **49 Python/data tests, 19 contract/bridge tests and 3 browser tests**, plus the production build and TypeScript checks. `scripts/test_offline_copy.py` checks the distributed source and samples with full datasets/model absent and external network denied, using the installed dependency environment.

## Repository and submission

The original implementation specification and architecture assets remain at the root. Bulk downloads, processed databases, trained binary models, local-chain state, runtime evidence and dependency directories are gitignored. Small attributed official records and measured experiment reports are shareable source assets.

[Architecture](docs/ARCHITECTURE.md) · [source attribution](ATTRIBUTION.md) · [competition conflicts](docs/COMPETITION_RULES.md) · [4:35 English demo script](docs/DEMO_SCRIPT.md) · [submission description](docs/SUBMISSION_DESCRIPTION.md) · [submission checklist](docs/SUBMISSION_CHECKLIST.md).

The verified public deadline is **October 25, 2026, 22:00 Asia/Taipei**. Eligibility and submission-window contradictions remain recorded; personal eligibility and authenticated submission availability require the entrant's review. The local prototype is prepared without public upload, paid deployment or contest submission. The public repository, recorded video and optional hosting remain publication steps.

Original code: [MIT](LICENSE). Upstream datasets retain their own terms and attribution.
