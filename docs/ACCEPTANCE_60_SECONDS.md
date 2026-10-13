# GridProof: 60-second judge path and acceptance

**Purpose:** a campus facilities manager chooses a feasible energy schedule, sees Carbon/Cost/Peak tradeoffs and checks that the report corresponds to its declared sources. Benchmark impact is modeled, not measured site abatement.

This is the acceptance script for the current product iteration. Passing technical steps alone does not establish that a non-engineer understood the product; the teach-back below needs an actual person. Public access remains pending authorization.

## One-minute golden path

Start the prepared local dashboard or an actual authorized live URL. Use **2025-09-01**, the bundled trained-model day. Keep 40 kWh battery and the original EV/lab workload for the first comparison.

| Time | Action | What a judge should understand |
| --- | --- | --- |
| 0–10 s | Read the opening user/problem statement and Carbon, Cost, Peak headline. | A campus manager has charging deadlines and a grid-import peak. GridProof makes a plan and checkable evidence. These deltas describe the selected historical scenario; the 122-day result is shown separately in Replay. |
| 10–25 s | Open Dispatch, choose a goal and run optimization if controls changed. | Forecasts feed the constrained optimizer. This is a real compute request using shipped historical sources/model, not an artificial live-AI animation. |
| 25–40 s | Switch Lowest Carbon, Lowest Cost, Lowest Peak and Balanced; inspect metrics and load curve. | The workload is unchanged. Lowest Carbon can have a higher peak; Lowest Peak can cost more. Balanced is a practical compromise, not best on every axis. Switching between already computed policies is labeled selection/replay, not a new solve. |
| 40–55 s | Open Trust Audit; generate/load evidence, verify local layers, then **Forge CI + rehash**. | Untouched evidence passes its local checks. New hashes alone cannot legitimize rewritten source values: Integrity may pass while Source Lineage rejects. |
| 55–60 s | Read the chain state and the source/simulation labels. | Sources are authentic cached grid data; the facility/tariff are simulated. On-chain verification is a separate real receipt read or visibly unavailable. |

For a slower network/host, use the full [4:35 recording workflow](DEMO_SCRIPT.md). Do not claim the one-minute path proves a fresh public cold-start meets 60 seconds.

## Receipt and offline branches

With a healthy local chain, **Load recorded release proof → Verify all local layers → Read recorded attestation** checks the fixed September 1 report and its current actual receipt. It must match this report's digest and exact scope. A scope record's numeric ID is a global registry ID, not a revision number; previous/replacement links and revocation status are actual contract fields. A changed new report cannot reuse the old receipt. Duplicate rejection is expected, with read-only inspection of the existing claim.

With no RPC, local verification and the deliberate source forgery still work; the chain must remain UNVERIFIABLE/NOT CHECKED. Open [offline/index.html](../offline/index.html) directly or the authorized static URL to explore recorded comparisons and attacks with the API/network blocked. It performs no new solve, provides its disclosed browser verification subset, and never claims a live attestation.

## Concrete acceptance and evidence

| Acceptance | Evidence required | Status to record |
| --- | --- | --- |
| Value understood within 60 seconds | A non-engineer can state who uses it, what decision changes and what blockchain checks. | Human teach-back pending; do not replace it with E2E counts. |
| Scheduling/three-goal tradeoff | Real compute request plus displayed same-workload policies and matching exported CSV/JSON. | Passed: goal switching, same captured metrics, 48-row CSV and selected-plan JSON, without an extra solve on goal switches. |
| Source forgery refused | Genuine v2 passes; CI rewrite plus new hash shows Source Lineage mismatch. | Passed; [rejection screen](assets/lineage-rejected.png) and actual browser record. |
| Chain online/offline behavior | Canonical real receipt when online; unavailable state with missing RPC; no old-receipt green after reset. | Existing 32 bridge checks passed; actual fixed local read VERIFIED; recorded offline flow passed with network blocked and no chain claim. [Receipt screen](assets/registry-verified.png). |
| Numbers attributable | Selected-day values match real comparison; full-period values match frozen 122-day CSV/summary; simulation labels visible. | Passed for selected/exported metrics; frozen model/benchmark/source assets unchanged. No benchmark rerun performed. |
| External judge access | Anonymous repository/video/authorized demo URLs open without local software or wallet. | Pending publication/account actions. |

Before filming, ask one person unfamiliar with the code to use the page for 60 seconds, then answer: **“Who is this for? What changes in the schedule? Why might Balanced beat Lowest Carbon for this user? What does the blockchain prove?”** Record elapsed time and their words. Pass only if they identify the manager, operational tradeoff and report commitment without calling modeled results measured abatement or a hash proof of truthful meters. If they miss a point, change the relevant label/first screen rather than commissioning another benchmark.

Keep success/forge/chain-unavailable screenshots and the actual 4:35 video once recorded. The release handoff is [RELEASE_OPERATIONS.md](RELEASE_OPERATIONS.md); account/publication actions remain explicit human steps.
