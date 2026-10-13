# GridProof demo — 4 minutes 35 seconds

**Deliverable: storyboard, exact English narration and recording instructions. No video has been recorded/uploaded.** Record 1920×1080 at readable zoom with a visible pointer. The 4:35 includes navigation and result pauses; rehearse and adjust pauses, not benchmark figures.

## Recording preflight

1. Use the documented local setup/build and `scripts/run_demo.ps1`; open `http://127.0.0.1:3000`. Keep API, dashboard and local chain healthy. Startup does not auto-attest. Inspect final verification logs; a historical pass is not a fresh pass.
2. Confirm four dates: `2025-01-15`, `2025-08-12`, `2025-09-01`, `2025-10-13`. Start September 1 with visible `lightgbm-past-only-v1`. January/August use seasonal fallback. The portable model ships; retrospective MAE is an outcome diagnostic, not decision-time information.
3. Keep default 20 kWp PV, 40 kWh battery and identical EV/lab work. Check peak-aware comparisons and the 122-day table. Prepare October 13 in a second tab.
4. Audit: **Generate evidence**, **Verify all local layers**, then **Forge CI + rehash**. Untouched v2 must pass the three offline layers. Rehashed forgery must pass Integrity but fail Source Lineage. Missing necessary source/anchor/model material must show `INCOMPLETE`, not full `VERIFIED`.
5. Chain recording is read-only. Enter a genuine existing local scope key and **Inspect existing scope**. Match its returned digest/transaction to the original report. A fresh v2 report is not automatically the old commitment. If the chain was reset, show `UNVERIFIABLE`; do not manufacture a green receipt.
6. **Read published Sepolia proof** currently reports unavailable/unverifiable because no public deployment exists. After separately authorized deployment only, substitute the real fixed proof and explorer transaction; judges need no wallet.
7. Open `offline/index.html` directly with networking off. Check recorded replay and attacks. It needs no Python/Node/API/wallet, performs no new solve and has narrower browser assurance than the complete Python verifier.

Do not change site/interval/category to bypass duplicate scope. Lookup verifies the existing commitment, not a new report. Public writes stay disabled.

## Storyboard and word-for-word narration

Read quoted narration only; screen instructions are unspoken. Keep **simulation**, **same workload**, **modeled exposure** and four layer names legible.

| Time | Screen and operation | Exact narration |
|---|---|---|
| 0:00–0:25 | Control Room: user problem, energy flows, Carbon/Cost/Peak. | “A campus manager must charge a fleet before departure, finish lab work and avoid a costly power peak. A carbon chart alone cannot schedule that work. GridProof produces a feasible plan and evidence another person can independently check. The objective is a useful decision, not a green number without operational limits.” |
| 0:25–1:00 | Dispatch: September 1, model/error/source labels; briefly show fallback then return. | “We use authentic historical Great Britain grid records, but the London campus, its devices and tariff are simulated. Weather is reanalysis and solar production is modeled. This date uses the trained LightGBM predictor; earlier dates use a labeled seasonal fallback. The model sees past observations and calendar features. Its forecast feeds the optimizer. Future actual intensity only scores the completed decision, and the error shown here is retrospective.” |
| 1:00–1:45 | Change EV deadline, compute, inspect SoC/jobs/status. Select impossible 08:00 deadline, show error, restore. | “The mixed-integer solver balances energy every half hour. It respects battery losses and bounds, charging power, exact vehicle demand and a contiguous lab job. The battery ends with its starting energy. Here I change a deadline and solve again. An impossible deadline produces a visible error. Peak-aware optimization adds a maximum-power objective and an optional cap. Its conservative zero-solar guard protects the power envelope without using future weather. Every policy is compared under the same workload and physical limits.” |
| 1:45–2:40 | Replay: 122-day table and tradeoff plot; October 13 comparison and half-hour replay. | “Across all one hundred twenty-two test days, peak-aware scheduling lowered total modeled emissions exposure by four point one six percent. Mean daily peak fell from thirty-four point zero five to eighteen point five two kilowatts, and illustrative cost fell by seven point nine seven percent. This gives up some carbon benefit to control peak. Four days still worsen carbon; October thirteenth is one. Total improvement and mean daily percentage are distinct. Seasonal prediction remains a strong baseline: the paired confidence interval includes zero, so we do not claim a reliable custom-AI advantage. The oracle uses unavailable future information.” |
| 2:40–3:45 | Audit: generate, verify local layers; forge CI and rehash; expand mismatch/original commitment failure. | “The report separates four checks: Integrity, Source Lineage, Physical Validity and On-chain Attestation. SHA256 checks committed bytes. The independent verifier also reconstructs original carbon records, prediction, solar conversion, load and tariff against separately pinned source anchors. It checks energy balance, job completion and arithmetic. Missing necessary sources mean incomplete assurance. Now we change carbon intensity to zero and recompute every hash. Integrity passes for the new bytes, but Source Lineage fails: the claimed values disagree with the pinned records. Against the original commitment, the hash fails too. This attack previously passed; the regression now rejects it. Legacy reports keep their historical bytes but do not receive new source assurance. None of these checks proves an external meter told the truth.” |
| 3:45–4:15 | Inspect genuine existing local scope/receipt, then pending published Sepolia proof. | “The registry permits one active exact site, time and category, with authorized revocation and replacement history. This read checks an existing local commitment, not the newly generated report. It does not bypass duplicates. Sepolia read-only support is prepared, but public deployment is pending. No wallet is required to inspect a published proof; an unavailable chain remains unverifiable.” |
| 4:15–4:35 | Offline HTML: recorded comparisons/replay/challenge and limitations. | “This self-contained backup lets a judge inspect recorded results without installing Python or Node. Complete verification and benchmark files are also provided. GridProof is a constrained, challengeable prototype. Validated meters, operational trials and measured climate outcomes are the next tests.” |

After an actual authorized Sepolia proof verifies, replace only the 3:45–4:15 narration:

> “The registry permits one active exact site, time and category, with authorized revocation and replacement history. This reads the fixed Sepolia proof and its actual transaction without a wallet. The displayed report digest matches the active record and canonical receipt. Existing scopes are inspected rather than silently reused for new reports. An unavailable or reorganized chain remains unverifiable.”

This replacement requires real successful verification, not example metadata. Say **local development chain** for 31337 and **Sepolia testnet** for 11155111. Claim no mainnet, certification or carbon credit.

## Figures to keep visible

| Frozen 122-day result | Correct value |
|---|---:|
| Peak-aware total exposure improvement | 4.1615%; headline 4.16% |
| Peak-aware mean daily improvement | 4.3024%; separate statistic |
| IID bootstrap 95% CI for total improvement | [3.7097%, 4.6132%] |
| Seven-day block CI for mean daily improvement | [3.7641%, 4.9132%] |
| Mean daily peak | Immediate 34.0531 → Peak-aware 18.5167 kW |
| Reduction of the mean peaks | 45.6241%; headline 45.62% |
| Mean illustrative cost | £61.7026 → £56.7849/day; −7.9701% |
| Peak-aware negative carbon days | 4/122 |
| Original hybrid | Total 5.8966%, mean daily 6.3651%, 7 negative days, mean peak 48.2275 kW |
| October 13 peak-aware outcome | 74.1675 vs Immediate 74.1444 kgCO₂; **−0.0312% carbon improvement** despite lower cost/peak |
| Peak-aware LightGBM minus seasonal | Mean daily +0.1819 percentage points; paired seven-day CI **[−0.1879, +0.5573]**, includes zero |

Sources: `experiments/competition_v2/summary.json`, `daily_results.csv` and `paired_forecast_ablation.json`. Frozen before this execution, after the earlier audit; no untouched preregistration or four-season claim.

## Recording and fallback

- Recording/upload/playback checks remain human account steps: [checklist](SUBMISSION_CHECKLIST.md).
- Verify 3–5-minute duration, units and real results. Do not splice a historical successful receipt onto a failed current query.
- Keep exported evidence, independent verifier, trusted anchors, offline HTML and the actual video. Lightweight HTML checks do not recreate complete predictor/job constraints or query a chain.
- If API/RPC fails, show its unavailable status then switch to labeled recorded replay. State backup date/version; do not describe it as a newly solved plan or fresh transaction.
