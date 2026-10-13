# Public deployment preparation

**Current status: prepared, not published or deployed.** The anonymous GitHub webpage/API returned 404 on 2026-10-13 at 06:45 UTC. No hosting account, public service, repository visibility change, push, contract deployment, public transaction, video upload or Devpost submission was performed in this preparation phase. External account steps are in [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).

## Chain configuration and fixed proof

Sepolia is Ethereum's recommended application testnet; its chain ID is **11155111**. It remains a test network, not proof of environmental certification. [Ethereum networks](https://ethereum.org/developers/docs/networks/), [viem official Sepolia definition](https://github.com/wevm/viem/blob/main/src/chains/definitions/sepolia.ts).

| Variable | Use | Public-service policy |
|---|---|---|
| `GRIDPROOF_CHAIN_NETWORK` | `local` or `testnet`; bridge default network | Choose explicitly; testnet means Sepolia only |
| `GRIDPROOF_CHAIN_ID` | API configuration expected chain; bridge independently enforces network chain | 31337 local / 11155111 Sepolia |
| `GRIDPROOF_LOCAL_RPC_URL` | HTTP loopback local RPC | Corrects old unused `GRIDPROOF_RPC_URL` naming |
| `GRIDPROOF_READ_ONLY` | `1` rejects all bridge writes including local | Required for a public service; API must also deny writable routes |
| `GRIDPROOF_ALLOW_CHAIN_WRITES` | API write permission; example0 | Keep0 publicly; local deliberate demonstrations require1 and read-only0 |
| `GRIDPROOF_SEPOLIA_RPC_URL` | Operator-supplied HTTPS RPC | Never caller JSON; URL userinfo rejected; do not expose provider keys/path/query to browsers |
| `GRIDPROOF_SEPOLIA_DEPLOYMENT_FILE` | Trusted fixed metadata JSON, relative paths resolved against workspace | Default `contracts/public/sepolia-registry.json`; absent means no claimed deployment |
| `GRIDPROOF_PUBLIC_PROOF_FILE` | Fixed proof index, workspace-relative | Default `contracts/public/fixed-proof.json`; absent means unavailable |
| `GRIDPROOF_SEPOLIA_PRIVATE_KEY` | Dedicated test-only signer for separate operator preparation CLI | Empty/absent in hosted verification; never `NEXT_PUBLIC`, API request, log or Git |

Hardhat's Sepolia configuration has **no accounts**. The public bridge constructs only a public client, never a wallet and never reads the signer key. It rejects attest/revoke/replace/deploy before RPC/signing. The separate signer helper can derive a reviewable public address from an operator environment secret; preparation never broadcasts. Primary implementation reference: [Hardhat configuration/secrets guide](https://hardhat.org/docs/guides/configuration-variables), [viem account implementation](https://github.com/wevm/viem/blob/main/src/accounts/privateKeyToAccount.ts).

```powershell
npm --prefix contracts run build
npm --prefix contracts run prepare:sepolia
# Optional READ-ONLY network check after operator config; no signer needed:
npm --prefix contracts run prepare:sepolia -- --rpc
# Optional separate operator address preparation; never on a hosted verifier:
npm --prefix contracts run prepare:sepolia -- --signer
```

The actual plan is written under ignored `contracts/runtime/sepolia-deployment-plan.json` with compiler/source/bytecode hashes, `PREPARED_NOT_DEPLOYED`, and `public_writes_available:false`. `--broadcast`/`--deploy` explicitly reject. No public deployment command is enabled during this phase. Placeholder `.example.json` files contain nulls and cannot verify as deployments/proofs.

After a separate reviewed authorization, an operator must supply the actual deployment address, transaction, captured block/hash, runtime bytecode SHA256 and ABI, and the reviewed fixed report's key/digest/registration transaction. Confirm source verification and real explorer links after deployment. These steps are pending, not completed by example metadata.

Public judges use no wallet, account or test ETH. The backend's fixed proof endpoint serves the actual evidence and calls read-only verification of the preconfigured tuple. Bridge JSON actions:

```json
{"action":"config","network":"testnet"}
{"action":"fixed-proof","network":"testnet"}
{"action":"verify","network":"testnet","expected_chain_id":11155111,"claim_key":"<actual key>","digest":"<independently computed SHA256>","transaction_hash":"<actual registration tx>"}
{"action":"lookup","network":"testnet","claim_key":"<existing key>","transaction_hash":"<actual tx>"}
```

`config` exposes only readiness booleans, chain/address/read-only mode and explorer base, with no RPC secrets. `fixed-proof` accepts no caller replacement for the trusted tuple. The index requires `schema_version:gridproof-public-proof-index/v1`, `network`, `chain_id`, real `claim_key`, `digest`, `transaction_hash`; optional evidence ID/URL identify the served report. A query may not change those fields inside fixed-proof mode.

Verification checks chain ID, runtime code, captured deployment block/receipt, active record/digest, registration event and successful canonical receipt. Sepolia requires at least two confirmations. With an actual registration hash it reads the receipt directly rather than scanning unbounded public event history. Missing hash/index, wrong chain, RPC outage, failed/reorganized receipts and absent events remain **UNVERIFIABLE**. A public RPC is still a trust boundary; independent providers/explorer checks strengthen assurance.

## Duplicate scope without a stuck demo

Local deliberate attest retains `REJECTED/DUPLICATE_ACTIVE_CLAIM`. It additionally returns `claim_key`, `existing_claim` with a freshly verified current receipt (or its explicit unavailable status), and `requested_digest_matches_existing`. This does **not** register or authenticate a changed new report. A different model/scenario cannot bypass the exact scope.

`lookup` returns a flat current-record verification object plus `verification_subject`, clearly distinguishing lookup from verification of a new report. UI offers read-only existing-record inspection; if digests differ, label that mismatch and show the previously committed evidence. Replacement requires a separately authorized original submitter and explicit revoke→replace history. Do not change site/category/time to manufacture uniqueness.

Local reset protection stays strict: captured deployment block hash/number, bytecode, canonical successful receipts and events must agree. Saved local receipts alone never produce live green verification after a reset. The initial preparation did not reset a running chain. Later, an interrupted local node was unavailable during integrated testing; its metadata was archived and a fresh local development registry was started. Historical receipts cannot verify on that new instance. See [release validation](VALIDATION.md) and its actual local evidence record.

## Actual preparation checks

- `npm test`: **32/32** contract/bridge cases passed, including unchanged local history/reset checks, duplicate receipt reuse without new-digest verification, fixed-index validation and public read-only/two-confirmation/wrong-chain/RPC configuration tests. Delivered actual output: [contract-tests.log](validation/contract-tests.log).
- Build/TypeScript typecheck passed; delivered actual logs: [contract-build.log](validation/contract-build.log), [contract-typecheck.log](validation/contract-typecheck.log). Sepolia Hardhat URL is lazy configuration, so absent credentials do not break local tests/builds.
- Actual read-only public RPC check used the URL supplied by the installed/official viem Sepolia chain definition, `https://11155111.rpc.thirdweb.com`: chain 11155111 and block 11904422 at `2026-10-13T06:56:51Z`. Only chain/block reads occurred; no signer was configured and no deploy/registration occurred. Endpoint availability is not guaranteed.
- Anonymous GitHub webpage/API returned 404; Devpost Rules direct HTTP 403/browser success recorded in [COMPETITION_RULES.md](COMPETITION_RULES.md).

Frontend/API hosting, persistence, rate limits and deployment profiles are prepared by the main implementation workstream. A public deployment should serve precomputed evidence without exposing a signer or mutable local write API; actual hosting remains pending authorization.

## Hosting files and local review commands

`Dockerfile.api`, `Dockerfile.web` and `compose.yaml` are now prepared. **They have not been executed in Docker or validated on Linux/cloud.** These are concrete configuration artifacts, not a successful deployment report.

- API image: Python 3.11, pinned requirements, native runtime libraries, Node 24 for the read-only chain bridge, backend/scripts/sample upstream bytes/trusted anchors/portable model and experiments. It listens on `0.0.0.0` and the host's `PORT` (default 8000).
- Web image: Node 24, pinned npm install and Next production build. `GRIDPROOF_API_URL` is a **build-time** argument for the Next API rewrite; use the intended API origin before building. It listens on `0.0.0.0` and `PORT` (default 3000).
- Compose intentionally publishes only `127.0.0.1:8000` and `127.0.0.1:3000`, so local review does not expose a public service. No Hardhat node, unlocked account or signer is bundled as a public service.

After installing Docker, the operator can review and run the local-only profile:

```powershell
docker compose config
docker compose up --build
# In another terminal, read health; do not deploy or attest:
Invoke-RestMethod 'http://127.0.0.1:8000/api/health'
```

For a host without containers, use a fresh Python 3.11 environment and Node 24, install the pinned dependencies, build the web frontend with its final API URL, and run Uvicorn/Next on the host-assigned port. README contains local setup commands. A clean Linux dependency install remains a required pre-publication check.

## Public service configuration and checks

| Setting | Hosted choice |
|---|---|
| `GRIDPROOF_READ_ONLY` | `1`; denies chain writes and enables bounded dispatch concurrency |
| `GRIDPROOF_ALLOW_CHAIN_WRITES` | `0`; no public attest/revoke/replace |
| `GRIDPROOF_CHAIN_NETWORK` | `testnet` only after actual reviewed Sepolia metadata is available; pending configuration must remain visibly unavailable |
| `GRIDPROOF_CHAIN_ID` | `11155111` for Sepolia; do not call local chain 31337 public evidence |
| `GRIDPROOF_API_URL` | API service origin supplied before the web production build; do not use the developer laptop's loopback URL |
| `GRIDPROOF_CORS_ORIGINS` | Exact allowed web origin(s), if cross-origin browser access is used; web API rewrites keep ordinary requests same-origin |
| `GRIDPROOF_STORAGE_PATH` | Review ephemeral `/tmp/gridproof/runs.sqlite3` versus a mounted persistent volume; generated reports are not durable merely because SQLite exists |
| `GRIDPROOF_SEPOLIA_PRIVATE_KEY` | Absent; never copy an operator signing environment into the hosted verifier |

Current application limits include a 12 MB declared-content-length guard and two concurrent compute requests in hosted read-only mode; this is not a complete abuse-control system. Configure actual reverse-proxy body limits/rate limits, timeouts and HTTPS, and measure cold-start behavior on the chosen host. Keep fixed proof/anchors/model available independently of ephemeral generated run storage. A public RPC outage must show `UNVERIFIABLE`.

Before seeking final authorization, complete a reviewable local release: final source/secrets/attribution check, clean Linux/container build, health and four demo dates, production browser flow, genuine evidence success and rehashed-forgery rejection, incomplete-source status, signed metadata/proof review without broadcast, and cold-start/persistence checks. Then obtain explicit permission for the particular visibility change/service/contract action. Do not infer permission from these commands or preparation documents.

## Offline and submission fallback

`offline/index.html` is a self-contained recorded replay that can be opened directly without Python, Node, RPC, a wallet or a network. It includes the four demo dates and final 122-day benchmark. Its lightweight browser checks cover recorded hashes, pinned source values and energy balance; complete model/job/source reconstruction remains the separate Python verifier. It performs no new optimization and supplies no live on-chain attestation.

Use the [demo script](DEMO_SCRIPT.md) for a 4:35 recording and the [submission checklist](SUBMISSION_CHECKLIST.md) for account actions. The video is still unrecorded, anonymous repository access remains unconfirmed, hosting/Sepolia are not deployed and Devpost is not submitted. If a live service fails, present labeled recorded results and explicit unavailable status rather than a fabricated successful query.
