# Local chain demonstration

This is a real Hardhat3 EVM development chain, labeled **LOCAL DEV CHAIN**, chain ID31337. It runs on loopback only, uses public development accounts and spends no money. No public explorer or public testnet is implemented.

Install and build with Node24:

```powershell
npm --prefix contracts ci
npm --prefix contracts run build
npm --prefix contracts test
npm --prefix contracts run typecheck
npm --prefix contracts run start:local
```

`contracts/scripts/start_local.ps1` and `start_local.sh` build and start the same node. Startup reuses a healthy existing node/deployment, writes node logs and PID under `contracts/runtime/`, and writes an actual deployment receipt/ABI/code digest to `contracts/deployments/local.json`. Startup does not attest any report. Hardhat's chain state lives in memory: after stopping/resetting it, old receipts cannot be verified until the evidence is deliberately registered on the new deployment. Ignore runtime metadata in source control.

The backend invokes `node contracts/scripts/bridge.mjs` with a JSON request on stdin and reads one JSON response from stdout. JSON is passed directly to a subprocess, never interpolated into shell code. Keep a90-second subprocess timeout on hosts with slow first imports. Individual RPC calls timeout after5 seconds and transaction receipt waiting after15 seconds.

```json
{"action":"health","network":"local","expected_chain_id":31337}
```

Health/verification are read-only. The default RPC is `http://127.0.0.1:8545`; `GRIDPROOF_LOCAL_RPC_URL` accepts another HTTP loopback URL only. `network:"testnet"` returns `UNSUPPORTED_NETWORK`, never a fake receipt.

For a deliberate attestation, the backend prepares an evidence bundle and computes SHA256 of its exact canonical bytes:

```json
{
  "action":"attest",
  "network":"local",
  "expected_chain_id":31337,
  "digest":"<actual SHA256 as 64 hex characters, optional 0x prefix>",
  "claim_scope":{
    "site_hash":"<nonzero 32-byte site hash>",
    "from_utc":"2025-09-12T00:00:00Z",
    "to_utc":"2025-09-13T00:00:00Z",
    "category":"modelled-grid-emissions-exposure"
  }
}
```

Placeholders above are explanatory, not valid hashes or fabricated transaction records. Timestamps are whole-second ISO UTC ending in`Z`. Category hash is SHA256 of the exact UTF8 category string. Scope key is Solidity `keccak256(abi.encode(bytes32 siteHash,uint64 fromUnix,uint64 toUnix,bytes32 categoryHash))`, independent of scenario/model/digest. The contract computes this key internally so callers cannot supply an alternative uniqueness key.

Successful writes return `ATTESTED`, an actual transaction hash, mined receipt, registration event and claim key. Receipt files are saved at `contracts/runtime/receipts/<transaction_hash>.json`. A repeat active exact scope returns `status:REJECTED` with `error.code:DUPLICATE_ACTIVE_CLAIM`, including when its scenario/model/evidence digest changes. Known authorization/scope/digest validation failures also reject the write explicitly. It does not silently reuse an old receipt.

Verification request:

```json
{"action":"verify","claim_key":"<returned key>","digest":"<recomputed SHA256>","transaction_hash":"<returned real transaction>","expected_chain_id":31337}
```

`transaction_hash` is optional; when present it must match the current active registration. The verifier checks chain ID, deployed bytecode digest, canonical successful deployment receipt, current active evidence digest, matching registry event and canonical successful registration receipt. A changed byte in the canonical evidence yields `HASH_MISMATCH`. Wrong chain, unavailable RPC, stale/failed transaction, incorrect contract, or missing event yields `UNVERIFIABLE`. A revoked/unknown scope yields `REVOKED`/`NOT_REGISTERED`.

Lifecycle actions are explicit:

```json
{"action":"revoke","claim_key":"<returned key>","reason_digest":"<SHA256 of reason>"}
{"action":"replace","claim_key":"<returned key>","digest":"<SHA256 of corrected canonical evidence>"}
```

Only the original submitter can revoke/replace. Replacement before revocation reverts; direct re-registration after revocation reverts. Numbered historical records and previous/replacement IDs preserve the original commitment and event history. Replacement emits a new registration and linked replacement event.

The independent end-to-end CLI consumes a real computed backend proof:

```powershell
node contracts/scripts/smoke-evidence.mjs <computed-evidence-json-path>
```

It independently reproduces `gridproof-canonical-json-v1/float-decimal-strings-9` encoding, hashes the UTF8 bytes, performs an actual registration, verifies its event/receipt, flips one byte and shows hash mismatch, changes model/scenario and proves duplicate rejection, and proves wrong-chain verification is unavailable. It preserves transaction-named smoke reports under `contracts/runtime/`. If correcting an existing commitment, an explicit `--replace "reason"` performs authorized revocation and replacement, preserving history; it never silently overwrites a record.

In the UI demo: prepare computed evidence, click **Attest on local chain**, inspect its receipt, independently verify, change a local copy of the evidence and show mismatch, then attempt another model/scenario over the same exact scope and show duplicate rejection. Do not describe the verified digest as a verified carbon credit or as proof that the hypothetical campus physically reduced emissions.

Dependency selection was checked against the official [Node.js support policy](https://hardhat.org/docs/reference/nodejs-support), [configuration guide](https://hardhat.org/docs/reference/configuration), and [viem/node:test guide](https://hardhat.org/docs/guides/testing/using-viem). Direct dependency versions and the full resolved dependency graph are pinned in `contracts/package.json` and `contracts/package-lock.json`.

The captured implementation run includes a real initial registration and explicit linked replacements for the simulated London campus on `2025-09-12`, ending with the frozen default-normalized code/model/source report. The final captured digest is `cb3b6f6a33b6bf1016e3c4b6662081bbdb7e4dec8a90c3b459265e19fcf56631`; its actual local transaction is `0xb3884600647c7cc2f9015aa8366f2323973431d29bb5b5f3e0cbb17f3e549dfe`, block `9`. [Chain worklog](CHAIN_WORKLOG.md) records every actual lifecycle transaction and check, including evidence/chain verification and duplicate rejection through the final REST API. These are historical records from that specific local run, not seed data that should be shown as currently verified after restarting the node. Root also captured a separate Jan15 UI transaction before final default normalization; the Sep12 block9 proof is the current final artifact snapshot.
