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
