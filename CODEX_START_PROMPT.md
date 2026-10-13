# CODEX START PROMPT — GridProof / IEEE ClimateChain Global Hackathon 2026

Paste all of this into Codex from an **empty new GridProof workspace**, with `IMPLEMENTATION.md` placed at the repository root. The agent should inspect relevant local tools and execute work immediately, **not merely draft a plan**.

---

You are the lead autonomous research/data/ML/full-stack/blockchain engineer for my solo entry to **IEEE ClimateChain Global Hackathon 2026**. The project is **GridProof — Trustworthy Carbon-Aware Microgrid Orchestration**, targeting top-three results. The competition is organized through IEEE Blockchain Türkiye and collaborators; my chosen official track is **Renewable Energy & Energy Trading**. The judging dimensions are climate impact, innovation, technical execution, practical usefulness and presentation. We must submit a public source repo, 3–5-minute video, description, and functional prototype by **2026-10-25 22:00 Taiwan time**. Codex is encouraged for rapid development but must not invent data or claim achievements it has not verified.

## START IMMEDIATELY: READ AND EXECUTE

Read `IMPLEMENTATION.md` **entirely**, including the competition eligibility/timing inconsistencies, architecture, data-source catalog, metrics, contract threat model, and mandatory test gates. It is the binding project specification. If missing, report that fact and request the file; do not substitute a random climate application.

Start by creating the project files and performing a genuine online **source discovery → download → integrity check → storage → schema profiling → demo data preparation** pipeline. If this environment has no Internet access, report the exact connection error and prepare tested downloader scripts, but **do not state files were downloaded**.

### PHASE A: SOURCE INVESTIGATION AND ACQUISITION (PRIORITY 1)

Visit and independently revalidate the official contest pages, the dataset APIs and licenses before accessing data. Record retrieval time in UTC, exact source URLs, access/terms, and any competition rule conflicts; if information has changed after 2026-10-13, prioritize the newer official announcement and preserve the older reference as a conflict.

**Official contest**
- https://ieee-climatechain-hack.devpost.com/
- https://ieee-climatechain-hack.devpost.com/rules
- https://ieee-climatechain-hack.devpost.com/updates
- https://ieee-climatechain-hack.devpost.com/project-gallery

**Dataset acquisition order**

1. **MUST DOWNLOAD** National Energy System Operator GB national carbon intensity 2025 historical time series: `actual`/`forecast` gCO2/kWh and UTC timestamps. Source https://www.neso.energy/data-portal/national-carbon-intensity-forecast and official API https://api.carbonintensity.org.uk/. First inspect pagination, API schema, range/query constraints and licensing. Download 2025 and 2026 year-to-date if modest in size, else deterministic chunks. Optionally fetch London region 13 regional historical series and explicitly distinguish from the national series. Record 30-min interval validity and actual missingness.

2. **MUST DOWNLOAD** NESO 2025 historic national demand + wind/solar outturn CSV: https://www.neso.energy/data-portal/historic-demand-data . A documented 2025 resource URL is `https://api.neso.energy/dataset/8f2fe0af-871c-488d-8bad-960426f24601/resource/b2bde559-3455-4021-b179-dfe60c0337b0/download/demanddata_2025.csv`. Inspect and handle settlement periods and DST; document any revisions/latency. Optional 2026 up-to-date sample.

3. **MUST DOWNLOAD** Open-Meteo London hourly weather history, 2025, including `temperature_2m`, `shortwave_radiation`, `cloud_cover`, `wind_speed_10m` and timestamp. Docs https://open-meteo.com/en/docs/historical-weather-api ; endpoint `https://archive-api.open-meteo.com/v1/archive?latitude=51.5074&longitude=-0.1278&start_date=2025-01-01&end_date=2025-12-31&hourly=temperature_2m,shortwave_radiation,cloud_cover,wind_speed_10m&timezone=UTC`. This is historical **reanalysis**, not decision-time weather forecast. Check https://open-meteo.com/en/terms (free for **noncommercial** and attribution). Use attribution and caching; do not overload service.

4. **MUST INVESTIGATE & TRY DOWNLOAD** PVGIS v5.3 solar hourly production/irradiance baseline for a hypothetical 20-kWp London rooftop, lat=51.5074, lon=-0.1278: https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/using-pvgis-5/api-non-interactive-service_en . Confirm available historical years first (do not assume 2025). Prefer `seriescalc`, `pvcalculation=1`, `peakpower=20`, explicit system loss/angle/aspect/outputformat. Preserve response metadata and source. Model 2025 PV separately as **simulated**, with Open-Meteo radiation and published engineering assumptions; never call it observed power.

5. **OPTIONAL SMALL DATASET** UKPN aggregated smart meter sample: https://ukpowernetworks.opendatasoft.com/explore/dataset/ukpn-smart-meter-consumption-lv-feeder/?tab=metas . Determine free sample API and schema, access rights, actual time range, units, licensing. Download only sample if permitted; skip rather than fabricate or subscribe. **DO NOT DOWNLOAD** full ~10GB historical London household corpus. For robust demo, construct deterministic, transparent synthetic campus fixed loads and EV/batch scheduling jobs, seed=42, and label `simulated` in every API/UI response.

6. **OPTIONAL** NESO historic generation mix https://www.neso.energy/data-portal/historic-generation-mix , regional national Carbon API city view and 2026 test. Only after core datasets are downloaded and validated.

### REQUIRED DATA ARTIFACTS

- `data/manifests/sources.json` as structured evidence: original URL, fetched UTC, current license and attribution, content type, response status, byte size, SHA256, row count, columns/types, coverage interval, granularity, units, timezone, missing rate, transformations, observed/forecast/synthetic tag, access limitations.
- `docs/DATA_CATALOG.md` human-readable tables and source citations + reproducible download commands + realistic estimates of disk/RAM use.
- `docs/COMPETITION_RULES.md` official regulations and all contradictions (students-only vs broad rules; October 5 open announcement vs October 25 start in Rules; participation certificate 10-winners slot vs all eligible participants) with links and exact verified times.
- `data/raw/` snapshots (gitignored), `data/processed/` normalized datasets (gitignored), and `data/sample/` **small legal-to-share deterministic sample**, attributed and clearly labeled.
- `scripts/discover_sources.py`, `fetch_neso.py`, `fetch_openmeteo.py`, `fetch_pvgis.py`, `fetch_ukpn_sample.py`, `validate_sources.py`, `build_snapshot.py` with retry/backoff, timeouts, ETags if possible, deterministic output, no passwords. Explicit licenses and host rate limits.
- UTC `[start,end)` half-hour index, timezone-safe converters, DST-aware GB settlement mapping, no date-shift bugs, schema checks and diagnostic charts.
- `docs/ASSUMPTIONS.md`: every solar, load, price, battery, charging assumption labeled. Tariffs are **illustrative** unless a real licensed price dataset is sourced; do not label hypothetical cost as an actual bill.
- A terminal **SOURCE AUDIT** output with proof, e.g. `NESO_CI_2025: status downloaded, size=N bytes, rows=N, sha256=<real>`, plus unresolved blockers. If any mandatory source is inaccessible, explain precisely and keep the system working via verifiably sourced cached fixture or explicitly simulated fallback.

### SOURCES & SCIENTIFIC INTEGRITY — NONNEGOTIABLE

Never claim that a dataset is on disk before testing file existence and checksum. Never invent URL endpoints, dates, data values, schema, benchmark results, download counts or official award rules. Do not access gated APIs without permitted credentials or scrape against terms. Do not mix 2013 household usage with 2025 grid intensity as if simultaneously observed. No future weather/actual grid intensity leaking into decision-time forecasts. Distinguish historical forecasts lacking issue-time provenance from true real-time point-in-time data. Do not describe optimized location-based electricity emissions exposure as certified physical avoided emissions, environmental credits or market-verified offsets. Blockchain hashes attest report integrity, not underlying meter truth.

### PHASE B: BUILD A VERTICAL SLICE (DO NOT STOP AT DATA DOWNLOADS)

After data acquisition, continue in the same task to scaffold the actual GridProof project. Use Python 3.11, FastAPI, DuckDB/Parquet, scipy.optimize.milp, Next.js/TypeScript/Tailwind/Recharts, Solidity/Hardhat 3/viem. Confirm versions with live upstream docs and use compatible pinned dependencies. Make installation on Windows practical (`.ps1` scripts) and provide Unix alternatives. Never access other unrelated repositories or copy proprietary app source.

**First working thin slice must do this:** select 2025 historical day with authentic GB carbon intensity; simulate clearly labeled London campus with 20-kWp PV + 40-kWh battery + EV deadlines + flexible lab batch; compute unmanaged baseline, cost-first and carbon-first MILP plans with full energy balance; return actual computed schedule and metrics from FastAPI; plot those in Next.js; display source attribution and units. Tests must verify all load jobs are completed, battery SoC constraints, kWh/kW conversions, solver status and no fake avoided-carbon claims.

**Then** implement historical ML with leakage-proof rolling validation and honest baseline comparisons; add the `GridProofRegistry.sol` with one active claim per `(site,time interval,category)` even if model/scenario ID changes; canonical SHA256 evidence verifier; run and show a **real local Hardhat chain transaction**; separately mark optional public testnet. Add duplicate replay and tamper tests. The 3–5-min video will demonstrate both functioning schedule optimization and independent proof verification.

### PHASE C: EVALUATION AND DEMO

Perform reproducible chronological test on held-out periods, no random shuffled splits. Report actual measured metrics, including when GridProof fails to beat baseline; compare at least 3 fair policies with same workload and deadline constraints. Build an elegant, fast, fully working four-page dashboard (Control Room, Dispatch, Replay, Trust Audit) and a deterministic offline demo fixture based on **previously downloaded official records** plus transparently synthetic site data. Every UI indicator distinguishes observed / forecast / simulation / local-chain; no fabricated 'verified' state. Create README, architecture Mermaid, source citations, threat model, 3–5 minute English video script and submission checklist. **Do not auto-submit, push public source, spend money, deploy onto paid resources or post publicly without explicit approval**; preparing these assets is allowed.

### PRIORITY & EXECUTION PROTOCOL

- **Start now; no unnecessary clarification.** Research + fetch + validate + scaffold, not just an outline.
- Keep commands/results/provenance in `docs/WORKLOG.md`; after each gate report exactly what works vs remains.
- Prioritize G0 data → G1 optimizer/API → G2 blockchain tests → G3 ML benchmarks → G4 UI → G5 presentation. Cut optional regional data or public chain before weakening credibility.
- Finish each implementation gate with runnable tests, error handling and `how to run` commands. If a package/tool/endpoint fails, diagnose and fix it or describe precise unresolved failure. Never leave a stub claiming finished.
- Don't train a giant model or download huge datasets for appearances; performance and technical defensibility matter more than model size.
- The goal is an exceptional submission with concrete measurements, defensible impact, a nontrivial mathematical engine, public auditability, excellent UX, and a 3–5-min demonstration — **not** imaginary climate benefits or empty architecture diagrams.

BEGIN PHASE A AND ACTUALLY EXECUTE IT NOW.
