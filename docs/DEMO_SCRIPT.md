# GridProof demo — 4 minutes 35 seconds

**Deliverable: storyboard, exact English narration and recording instructions. No video has been recorded/uploaded.** Record 1920×1080 at readable zoom with a visible pointer. The 4:35 includes navigation and result pauses; rehearse and adjust pauses, not benchmark figures.

## Recording preflight

1. Use the documented local setup/build and `scripts/run_demo.ps1`; open `http://127.0.0.1:3000`. Keep API, dashboard and local chain healthy. Startup does not auto-attest. Inspect final verification logs; a historical pass is not a fresh pass.
2. Confirm four dates: `2025-01-15`, `2025-08-12`, `2025-09-01`, `2025-10-13`. Start September 1 with visible `lightgbm-past-only-v1`. January/August use seasonal fallback. The portable model ships; retrospective MAE is an outcome diagnostic, not decision-time information.
3. Keep default 20 kWp PV, 40 kWh battery and identical EV/lab work. Rehearse **Lowest Carbon → Lowest Cost → Lowest Peak → Balanced**. The displayed numbers, curves, exported schedule and generated evidence must use the selected policy. Goal switching selects computed results; changed scenario controls require a real Run optimization. Restore 40 kWh after the live change before referring to frozen full-period results. Prepare October 13 in a second tab.
   Cost-first uses tariff/calendar PV without a carbon-model objective. Immediate is an earliest-job heuristic. Balanced/Hybrid use the carbon prediction only with a positive carbon weight. Keep those current flow/export labels visible rather than implying every policy uses AI.
4. Audit: **Generate evidence**, **Verify all local layers**, then **Forge CI + rehash**. Untouched v2 must pass the three offline layers. Rehashed forgery must pass Integrity but fail Source Lineage. Missing necessary source/anchor/model material must show `INCOMPLETE`, not full `VERIFIED`.
5. Chain recording is read-only. Click **Load recorded release proof**, then **Verify all local layers** and **Read recorded attestation**. This loads the fixed September 1 release report, separate from a newly solved report. Match its returned digest/transaction to that exact report. **Inspect existing scope** remains available for other genuine records. A fresh v2 report is not automatically the old commitment. If the chain was reset, show `UNVERIFIABLE`; do not manufacture a green receipt.
6. **Read published Sepolia proof** currently reports unavailable/unverifiable because no public deployment exists. After separately authorized deployment only, substitute the real fixed proof and explorer transaction; judges need no wallet.
7. Open `offline/index.html` directly with networking off. Check recorded replay and attacks. It needs no Python/Node/API/wallet, performs no new solve and has narrower browser assurance than the complete Python verifier.

Do not change site/interval/category to bypass duplicate scope. Lookup verifies the existing commitment, not a new report. Public writes stay disabled.

## Storyboard and word-for-word narration

Read quoted narration only; screen instructions are unspoken. Keep **simulation**, **same workload**, **modeled exposure** and four layer names legible.

| Time | Screen and operation | Exact narration |
|---|---|---|
| 0:00–0:25 | Control Room: campus problem, three-step path, four goals and selected-day deltas. | “Campus managers need vehicles charged on time without creating a costly power peak. GridProof compares feasible schedules for carbon, cost and peak, then lets reviewers challenge their evidence. A separate blockchain commitment preserves the report's identity and correction history. These are simulated operational outcomes.” |
| 0:25–1:00 | Choose a goal → Dispatch: September 1 model-to-solver flow and source labels. | “This prototype uses authentic historical Great Britain grid observations and a simulated London campus. Solar production and tariff costs are modeled. September first uses our trained LightGBM predictor, which sees past records and calendar features. Its forecast suggests cleaner intervals; a separate constrained optimizer creates the schedule. Actual future intensity scores the historical outcome afterward. The model comparison and forecast error are available in the technical details.” |
| 1:00–1:45 | Switch the four goals; point to changed curves and deltas. Change battery to 60 kWh and Run optimization; restore 40 and rerun. Download selected CSV. | “There is no single best outcome. Lowest Carbon prioritizes forecast exposure. Lowest Cost targets the tariff. Lowest Peak uses a conservative power envelope without carbon forecasts. Balanced trades carbon, cost and peak. These buttons select genuine computed policies under the same workload. Changing battery capacity sends a real solve request. Vehicles still meet their energy and deadline requirements, the lab stays contiguous, and battery energy is conserved. The CSV exports this selected schedule's forty-eight intervals for a facilities manager to review.” |
| 1:45–2:40 | Compare schedules → Replay: finite trade-off map, full-period results, then October 13 negative case and half-hour replay. | “This map compares the policies on one day; it is not a complete Pareto frontier. Our frozen evaluation covers all one hundred twenty-two test days. Balanced lowers total modeled emissions exposure by four point one six percent, average daily peak by forty-five point six two percent, and illustrative cost by seven point nine seven percent against Immediate. The original hybrid gives more carbon benefit but a higher peak. Four days still worsen carbon. October thirteenth is one, shown openly here. These benchmark averages are separate from the selected-day values and are not measured field savings.” |
| 2:40–3:45 | Challenge the evidence → Audit: select Balanced, Generate evidence, view scope and original CI, verify, Forge CI + rehash; inspect rejected mappings. | “This report identifies the site, time, policy and first source-derived carbon value. Three local checks answer different questions. Integrity checks the bytes. Source Lineage independently reconstructs input values from pinned source snapshots and the trained model. Physical Validity checks energy balance, deadlines and arithmetic. Now the attack sets carbon intensity to zero and recomputes the hashes. The new bytes match their new hash, but Source Lineage rejects the invented values. Against the original commitment, the hash also fails. Missing necessary source material produces incomplete assurance. We show the rejection because a climate report should survive a deliberate challenge, not merely look credible.” |
| 3:45–4:15 | Load recorded release proof, verify local layers, read recorded attestation; show actual scope/history fields before collapsed JSON. | “On-chain Attestation is a separate receipt read. This fixed report matches the active commitment on our local development chain. Its scope permits one active report, with authorized revocation and linked corrections. The displayed history comes from actual contract fields. A changed report cannot borrow this receipt. Sepolia read-only release is prepared but not deployed. Neither hashes nor blockchain certify truthful meters.” |
| 4:15–4:35 | Offline HTML: goal switching, recorded replay, export and challenge; show NOT CHECKED chain status. | “The standalone backup keeps recorded comparisons, exports and source challenges usable without Python, Node, an API or a wallet. It performs no new solve and no chain query. GridProof joins an operational energy decision with evidence someone else can inspect. Public delivery and field trials are the next steps.” |

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
