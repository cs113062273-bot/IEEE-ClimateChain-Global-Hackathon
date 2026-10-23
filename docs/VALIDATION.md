# GridProof upgrade validation

Release checks ran on Windows with Python 3.11 and Node 24. These are actual local results; Docker/Linux/cloud execution, public deployment, video upload and Devpost submission are separate pending actions.

| Check | Result | Record |
| --- | --- | --- |
| Python engine, source, peak, judge API and lineage tests | 91 passed; one existing Starlette/AnyIO deprecation warning | [python-tests.log](validation/python-tests.log) |
| Contract and bridge tests | 32 passed | [contract-tests.log](validation/contract-tests.log) |
| Solidity build / TypeScript | Passed | [build](validation/contract-build.log), [typecheck](validation/contract-typecheck.log) |
| Browser E2E / offline / responsive | 6 passed on Microsoft Edge | [browser-e2e.log](validation/browser-e2e.log) |
| Source audit | Passed | [source-audit.log](validation/source-audit.log) |
| Offline isolated source copy | Four dates, seven policies each; complete source lineage; network blocked | [offline-source-copy.log](validation/offline-source-copy.log) |
| New Python dependency installation | Pinned lockfile installed into a new environment; pip check passed | [dependency check](validation/clean-python-install.log) |
| Fresh Git clone | Passed on exact source commit a29daadc79af054a4eeb33dddc86e6b74e24b74a: 91 tests, four demo dates, standalone evidence, source audit, two offline npm installs and both builds/typechecks | [JSON](validation/fresh-clone.json), [actual output](validation/fresh-clone.log) |
| Full benchmark consistency | 112 groups / 3,873 checks passed; old 120 policy-day values unchanged | [independent review](BENCHMARK_CONSISTENCY.md) |
| Production build / frontend typecheck | Passed in original checkout and fresh clone | [production-build.log](validation/production-build.log), [fresh-clone.log](validation/fresh-clone.log) |
| Secrets scan | No common credential patterns found; bounded scan, not complete security proof | [secrets-scan.json](validation/secrets-scan.json) |

## Failures retained and corrected

- An intermediate frontend typecheck caught a duplicated optional `digest` property during integration. The duplicate was removed; typecheck and production build subsequently passed. No test was deleted.
- The fresh-clone test invocation initially used nonexistent `data/tests`, so no tests ran. The correct command `python -m pytest backend/tests scripts/tests -q` then passed all 91 tests in the newly installed pinned Python environment. The [failed attempt](validation/fresh-clone-first-attempt.log) and [corrected output](validation/fresh-clone-python-tests.log) are both retained. The other eleven clone checks passed unchanged.
- The first final E2E run had four passes and one failure because the interrupted local node was unavailable. The UI correctly returned UNVERIFIABLE, while the test required a working real chain. [Original failed log](validation/e2e-failed-rpc.log) is retained.
- A fresh local development node/registry was started for the requested local testing. Historical deployment metadata was archived before restart; old receipts are not claimed to verify on this new chain. The unchanged chain test subsequently exercised a fresh actual registration, read verification and duplicate rejection.
- Benchmark sensitivities retained 610 infeasible rows, 610 rejected-input rows and 195 fallbacks. These are outcomes, not removed tests. At least 195 candidates were rejected by replay constraint checks; only returned fallback schedules have zero violations. Rejected residual magnitudes were not retained.

## Trust boundaries

Local VERIFIED means Integrity + Source Lineage + Physical Validity. On-chain Attestation is separate and remains NOT CHECKED without a canonical current receipt. Old v1 is INTEGRITY_ONLY. Required-source or external-anchor absence is INCOMPLETE. An untrusted rewritten source cannot become trusted merely by changing its reported hash.

Only the local test chain was exercised. No public website, Sepolia deployment, Git push, visibility change, video upload or formal contest submission occurred.

The captured September 1 v2 release proof, its three independently verified offline layers, rehashed forgery rejection, actual local registration/read and duplicate rejection are retained in [evidence-verification.json](validation/evidence-verification.json). This is a historical test record from that particular chain instance. A stopped or restarted local node cannot turn it into a current valid receipt; the live reader must query and verify the current deployment and record.

The final preview was restarted after another user interruption stopped local services. Its prior deployment metadata was archived, and the same fixed release report was deliberately registered on the fresh local registry at block 2. A real read verified the exact digest, followed by duplicate rejection: [local-preview-attestation.json](validation/local-preview-attestation.json). No public chain was contacted by these writes. The preview at `http://127.0.0.1:3000` was healthy when captured; future node resets still invalidate that instance's receipts.

## Clean-checkout scope

The clone initially had no raw/processed bulk data, pickle models, chain runtime or node_modules. It used the genuinely new Windows Python environment installed from `requirements.lock.txt`; both npm packages were installed independently with `npm ci --offline --no-audit --no-fund` from cached packages. Pinned original source bytes and portable trained trees are intentional release assets. The fixture SHA256 stayed `5c403ff1c82600b7c2838a98a5adbaf0bc82c20d66a2e67a8d018268d2bdb4f0` throughout.

This verifies packaging, clean dependency installation and local demo/evidence reproduction. It does not claim a new Linux/container installation, source reacquisition, model retraining, full benchmark rerun, public hosting, or browser/chain testing inside the clone. Those boundaries and the separate original-checkout tests are recorded explicitly.

## Subsequent product-focused iteration

The above full suite and exact clone belong to the preceding source-lineage/engine release. The subsequent UI/bridge iteration preserves those engine, source, model, benchmark and proof bytes and validates only affected behavior. [championship-validation.json](validation/championship-validation.json) records the final three affected browser workflows, three unchanged workflow passes from the integrated run, 32 existing chain/bridge cases, production build/typecheck, current actual local read, unchanged artifact fingerprints and retained failures. It does not pretend the older clone contains the new UI or that human 60-second understanding was measured.

[Product changes and direct answers](CHAMPIONSHIP_ITERATION.md), [judge acceptance](ACCEPTANCE_60_SECONDS.md) and [release operations](RELEASE_OPERATIONS.md) provide the current handoff.


## Service-readiness release — 2026-10-19

The new main product and original research routes were verified on the production Next.js build, with the local FastAPI and development EVM running. No public deployment or real equipment control was performed.

- **104 Python/data tests passed** (`backend/tests` and `scripts/tests`), including early readiness, same-asset baselines, outcome-blind decisions, executed EV/battery/SoC preservation, infeasible recovery, disconnect shortfall, event order, and independent verification rejecting a rehashed rewritten prefix. One existing Starlette/AnyIO deprecation warning remains.
- **32 contract/bridge tests passed**. Contract code was unchanged. The fixed release proof was deliberately registered on this local development chain to satisfy the existing recorded-receipt regression; its receipt was read live. This is not a public attestation or an attestation of the new service plan.
- **8 browser workflows passed** in headless installed Microsoft Edge against the production build. Existing policy selection, exports, replay, offline mode, forgery and local-chain tests remain. New workflows cover service → real replan → matching export/evidence → rehashed forgery rejection, plus infeasible input → no stale exports → early disconnect → explicit later-deadline acceptance → successful replan.
- Desktop 1366/1440px and 390px phone screenshots were actually inspected. The new UI has no page overflow at 390px; the strategy table intentionally scrolls inside its region. A global legacy table background leaked into the first screenshot and was fixed with scoped styles. Chart entrance animation was disabled so every captured curve represents the complete day. Screenshots: [workspace](assets/readiness-desktop.png), [event](assets/readiness-event.png), [evidence rejection](assets/readiness-evidence.png), [impossible request](assets/readiness-infeasible.png), [phone](assets/readiness-mobile.png), [accepted recovery on phone](assets/readiness-recovery-mobile.png).
- Frontend typecheck and optimized production build passed. Source audit passed in the distributed-fixture mode. Bulk acquisition paths are absent and explicitly reported; independently pinned original snapshot bytes are deliberately included elsewhere in the release and used by the experiment. No fresh full-data acquisition is claimed.
- **6,160 evaluation rows** completed in **305.813 s**. All original 122-day nominal peak-aware carbon/cost/peak values reproduce with maximum absolute difference **0**. The report asserts code hashes, row uniqueness, coverage, revised-demand delivery accounting and legacy consistency. Four new fixed synthetic configurations each have 122/122 valid protected schedules; all failure rows remain in the report.
- The exploratory real product recovery study ran in **37.537 s**: 36 requests satisfy the original revised demand/deadline; the other 86 become feasible only if the manager explicitly accepts a 30-minute extension. No repeated-test tuning or independent historical validation claim is made.

Retained failures during implementation: missing npm dependencies and uncompiled Solidity artifacts initially prevented the old startup command from launching; pinned installs and the contract build resolved that environment problem. The first new Python test imported the independent verifier under the wrong function name and was corrected before rerunning. The first new browser prefix assertion used exact floating equality and failed on `20` vs `20.000000000000007`; the final assertion uses 1e-7 precision and retains the physical tolerance. The first evaluation incorrectly represented a rejected event as zero prior delivery; its files are retained under `.runtime/service-readiness-first-pass`, and the final evaluator explicitly keeps the previous controls and counts the 6 kWh revised-demand deficit. No nominal policy selection was changed by that reporting fix.

The new code has not undergone a new clean-clone installation or Linux test. Historical fresh-clone evidence above applies to its stated earlier release. A real operator's teach-back, device response, continuous multi-day operation, and independent public commitment timing remain untested. See [engineering and results](READINESS_ENGINEERING.md).


Final targeted checks after the full suite: the new service report for 2025-08-12 was actually registered, read as VERIFIED and rejected on duplicate registration in the new product UI. [Receipt and rejection record](validation/readiness-local-chain.json) and [screenshot](assets/readiness-local-receipt.png) capture this local instance; it remains a historical test record after node resets. A further 320px check found tab text overflowing by a few pixels, fixed it with wrapping narrow-screen tabs, rebuilt/restarted production, and confirmed all three workflow screens plus the forged-evidence result have no page overflow: [responsive record](validation/readiness-responsive.json), [320px capture](assets/readiness-320px.png). The two affected browser workflows were rerun and passed after final UI-state fixes. Old research screenshots were restored to their original historical bytes; the new release has separate readiness screenshots.

## Workplace car-park release — 2026-10-19

Run on this Windows workstation (Python 3.11.14, Node 24, Microsoft Edge via Playwright) after relaunching with `.venv/Scripts/python.exe scripts/run_demo.py` (API and production `next start`; the existing local chain on 8545 was reused).

| Check | Result |
|---|---|
| `pytest backend/tests scripts/tests` | 129 passed (104 pre-existing + 25 new car-park tests), 1 pre-existing Starlette/AnyIO deprecation warning |
| `npm --prefix frontend run build` | Passed; TypeScript clean; routes `/`, `/readiness`, `/research`, `/dispatch`, `/replay`, `/audit` |
| `npm --prefix frontend run test:e2e` | 10 passed: 2 new car-park flows, 2 readiness, 3 competition, 3 workflow |
| `npm --prefix contracts test` | 32 passing |
| Live registry | A verified car-park record registered and read back `VERIFIED`; a second record for the same site-day returned `DUPLICATE_ACTIVE_CLAIM` |
| Viewports | 1440/1366 px desktop, 390 px and 320 px without horizontal scroll; dark colour scheme inspected |
| Evaluation | Validation selection then single 2024 test (185 days, 5,656 sessions). A later reproduction after line-ending normalisation matched all 32,566 numeric rows apart from wall-clock timing; recorded code hashes match the working tree |

The car-park flow test checks that tiles equal the API computation, that only cars plugged in by 09:30 appear in the controller view, that a 70 kW limit announced at 09:30 leaves all earlier energy unchanged and holds the cap, that a declared departure is applied, that switching strategy recomputes on the same day, that the 185-day headline matches `/api/carpark/results`, that all four record layers verify, that the exported JSON carries the on-screen run ID, and that both forgeries are rejected.

Not verified: a human teach-back, a public deployment, behaviour on a fresh machine without the session download, or any real charger.

### Review follow-up — same day

An external review reproduced a forgery that passed all four layers: a 34-car record reduced to 1 car, recomputed and re-hashed. Source correspondence checked that each listed car was a real site session but not that every servable site session that day was listed. The verifier now checks both directions; a third built-in forgery ("leave out the drivers who were short") and a regression test for the 34-to-1 case are rejected by source correspondence while genuine records still verify. Overclaiming wording ("every driver charged", "fully charged") was replaced with "requests met in full", with the request defined as the energy each real session took. Clipping counts (383 of 5,671 test sessions capped, 15 dropped, 97 above 11 kW) are disclosed. The fleet readiness and research pages are unlinked from the product and carry an archive banner. Re-run after these changes: 130 Python tests passed, 10 browser tests passed on the rebuilt production app. No evaluation outputs changed; the hashed evaluation code was not modified.

### Post-review follow-up — decision-time inputs and simple personal-history baselines

Protocol `experiments/carpark_followup/protocol.json` written first; selection per model family on 2023 H2; 2024 evaluated (exploratory, the year had been examined). `scripts/evaluate_carpark_followup.py` reproduces the published pre-registered paired results exactly (+1.892 / +1.930 / +1.292 drivers per day at 100 / 120 / 150 kW) as an internal consistency check. The product now builds cars with decision-time inputs (`backend/app/fleet/inputs.py`: fixed 11 kW, declared uncapped request, no drops); the verifier accepts that transform and requires every site session to be present. After rebuilding and relaunching: 131 Python tests passed, 10 browser tests passed, no horizontal scroll at 390 px on the new results view.
