# GridProof upgrade validation

Release checks ran on Windows with Python 3.11 and Node 24. These are actual local results; Docker/Linux/cloud execution, public deployment, video upload and Devpost submission are separate pending actions.

| Check | Result | Record |
| --- | --- | --- |
| Python engine, source, peak, judge API and lineage tests | 90 passed; one existing Starlette/AnyIO deprecation warning | [python-tests.log](validation/python-tests.log) |
| Contract and bridge tests | 32 passed | [contract-tests.log](validation/contract-tests.log) |
| Solidity build / TypeScript | Passed | [build](validation/contract-build.log), [typecheck](validation/contract-typecheck.log) |
| Browser E2E / offline / responsive | 6 passed on Microsoft Edge | [browser-e2e.log](validation/browser-e2e.log) |
| Source audit | Passed | [source-audit.log](validation/source-audit.log) |
| Offline isolated source copy | Four dates, seven policies each; complete source lineage; network blocked | [offline-source-copy.log](validation/offline-source-copy.log) |
| New Python dependency installation | Pinned lockfile installed into a new environment; pip check passed | [dependency check](validation/clean-python-install.log) |
| Fresh Git clone | Final source-commit check pending completion | Final record will be linked below |
| Full benchmark consistency | 112 groups / 3,873 checks passed; old 120 policy-day values unchanged | [independent review](BENCHMARK_CONSISTENCY.md) |
| Production build / frontend typecheck | Passed; final source clone build is also checked separately | Fresh-clone record |
| Secrets scan | No common credential patterns found; bounded scan, not complete security proof | [secrets-scan.json](validation/secrets-scan.json) |

## Failures retained and corrected

- An intermediate frontend typecheck caught a duplicated optional `digest` property during integration. The duplicate was removed; typecheck and production build subsequently passed. No test was deleted.
- The first final E2E run had four passes and one failure because the interrupted local node was unavailable. The UI correctly returned UNVERIFIABLE, while the test required a working real chain. [Original failed log](validation/e2e-failed-rpc.log) is retained.
- A fresh local development node/registry was started for the requested local testing. Historical deployment metadata was archived before restart; old receipts are not claimed to verify on this new chain. The unchanged chain test subsequently exercised a fresh actual registration, read verification and duplicate rejection.
- Benchmark sensitivities retained 610 infeasible rows, 610 rejected-input rows and 195 fallbacks. These are outcomes, not removed tests. At least 195 candidates were rejected by replay constraint checks; only returned fallback schedules have zero violations. Rejected residual magnitudes were not retained.

## Trust boundaries

Local VERIFIED means Integrity + Source Lineage + Physical Validity. On-chain Attestation is separate and remains NOT CHECKED without a canonical current receipt. Old v1 is INTEGRITY_ONLY. Required-source or external-anchor absence is INCOMPLETE. An untrusted rewritten source cannot become trusted merely by changing its reported hash.

Only the local test chain was exercised. No public website, Sepolia deployment, Git push, visibility change, video upload or formal contest submission occurred.
