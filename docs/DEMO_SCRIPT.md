# English demo script — 4 minutes 35 seconds

Record the local dashboard at 1920×1080. Use the cached August 12, 2025 day. Rehearse the chain segment on the other sample day first: an active scope cannot be silently registered again. Start a clean local chain for the final recording only if you intend to discard that development chain; existing proofs then become unavailable. Never substitute a recorded receipt for current RPC verification.

## 0:00–0:25 — A decision you can inspect

**Screen:** Control room, numerical campus twin.

“Energy managers have flexibility: vehicle charging, battery storage and work that can run at different times. But a carbon chart alone does not give them a feasible plan, or evidence somebody else can check. GridProof connects public grid records, a physical scheduling model and an independent proof of the resulting report.”

## 0:25–1:10 — Authentic records, explicit assumptions

**Screen:** Grid carbon outlook; then Trust audit source provenance.

“This demonstration uses authentic half-hourly national Great Britain carbon-intensity data from NESO. The campus is hypothetical, in London. Its rooftop, battery, fixed demand, vehicles and lab batch are transparently simulated. Weather comes from Open-Meteo historical reanalysis, and the photovoltaic baseline comes from JRC PVGIS. Acquisition manifests record URLs, licences, timestamps, file sizes and SHA256 fingerprints.

“Historical weather is not a forecast. Our decision predictor uses observations strictly before the decision cutoff. Future actual intensity is used afterward to score the plan. Provider forecast records are reported separately because their historical issue times are unverified.”

## 1:10–2:15 — Change a constraint, compute a schedule

**Screen:** Intelligent dispatch. Change battery size, run optimization, inspect EV schedule and SoC. Select an infeasible early deadline, show the error, then restore and recompute.

“Here are the actual computed schedules. The optimizer is a mixed-integer program using SciPy and HiGHS. It enforces energy balance every half hour, charging power, battery efficiency, state-of-charge bounds, EV energy and deadlines, and one contiguous lab batch. Stored energy ends where it began, so the report cannot borrow energy from tomorrow.

“I can change the battery size or a vehicle deadline and recompute. The same jobs and device limits are used for immediate charging, cost-first, carbon-first and the hybrid policy. Costs use an illustrative tariff, not a customer’s electricity bill.

“An impossible deadline produces an explicit error. The last valid dispatch stays visible. A convincing climate demo must make failure visible as well as success.”

## 2:15–3:05 — Replay the outcome fairly

**Screen:** Digital twin & replay. Move scrubber and reproduce day; show comparison and held-out report.

“The replay keeps the selected workload and battery decisions fixed. It balances imports against radiation-derived simulated solar and scores imported energy using historical actual carbon intensity. This is modeled location-based emissions exposure, not proof of causal physical avoided emissions.

“The policies share the same workload. The report includes chronological training, validation and held-out test periods, baseline forecasts, multiple scheduling policies and day-level uncertainty intervals. We preserve non-improving days. A separate oracle uses perfect future information; it is a benchmark ceiling, not deployable performance.”

## 3:05–4:05 — Recompute, commit, challenge

**Screen:** Trust audit. Generate evidence, recompute in browser, deliberately attest on local chain, verify, tamper with copy and recompute; attempt duplicate.

“This evidence contains the input snapshot, parameters, source fingerprints, forecast method, dispatch and results. The browser independently canonicalizes the JSON and computes SHA256. The Python verifier also reconstructs the arithmetic and physical constraints.

“This button records that fingerprint on a real local EVM chain. Here are the actual transaction, contract and scope key. The registry allows one active claim for a site, interval and category. Changing the scenario or model does not bypass that rule. Revocation and replacement retain their history.

“Now I alter a copy. Verification fails. An unavailable RPC is also reported honestly. Blockchain protects the integrity of a committed report; it does not prove that a meter, rooftop or physical climate benefit exists.”

## 4:05–4:35 — Adoption and credibility

**Screen:** Return to Control room; source badges visible.

“GridProof gives a campus, fleet or small industrial operator a concrete schedule and a reproducible explanation of its tradeoffs. Its climate value is an operational hypothesis that can be tested with validated meters. The innovation is the complete data-to-decision-to-evidence chain. The working optimizer and registry demonstrate technical execution, the controls support practical use, and the replay makes the method clear. Next steps are point-in-time weather forecasts, measured facilities, and independently validated field results.”

Avoid reading fixed savings numbers from this script. Narrate the current computed values shown in the application. Do not say “certified”, “carbon credits”, “field trial”, “testnet” or “AI outperforms NESO” unless independently established.
