// Independent report-byte hashing and actual local EVM integration demonstration.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { executeRequest, errorResult, sha256, stringify, computeScope } from './chain.mjs';

function canonical(value) {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number' && Number.isSafeInteger(value)) return JSON.stringify(value);
  if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
  if (value && typeof value === 'object') {
    const keys=Object.keys(value).sort();
    if (keys.some(key=>!/^[\x00-\x7f]*$/.test(key))) throw new Error('Canonical object keys must be ASCII');
    return '{'+keys.map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
  }
  throw new Error('Evidence must contain normalized decimal strings, finite safe integers, JSON strings/booleans/null');
}
if (!process.argv[2]) throw new Error('Usage: node contracts/scripts/smoke-evidence.mjs <backend computed evidence JSON path> [--replace "reason"]');
const inputPath=resolve(process.argv[2]);
const proof=JSON.parse(await readFile(inputPath,'utf8'));
assert.equal(proof.evidence.canonicalization,'gridproof-canonical-json-v1/float-decimal-strings-9');
const canonicalJson=canonical(proof.evidence);
assert.equal(canonicalJson,proof.canonical_json,'Independent Node encoder must reproduce backend canonical bytes');
const digest=sha256(Buffer.from(canonicalJson,'utf8'));
assert.equal(digest,proof.digest,'Independent Node SHA256 must match backend digest');
const safeCall=async request=>{try{return await executeRequest(request);}catch(error){return errorResult(error,request.action);}};
const base={network:'local',expected_chain_id:31337};
const replaceIndex=process.argv.indexOf('--replace');
let revocation;
if (replaceIndex>=0) {
  const reason=process.argv[replaceIndex+1];
  if (!reason || reason.startsWith('--')) throw new Error('Explicit replacement requires a nonempty reason argument');
  revocation=await safeCall({...base,action:'revoke',claim_key:computeScope(proof.evidence.claim_scope).claimKey,reason_digest:sha256(reason)});
  assert.equal(revocation.ok,true,`Authorized revocation failed: ${stringify(revocation)}`);
}
const attestation=await safeCall(replaceIndex>=0?{...base,action:'replace',claim_key:computeScope(proof.evidence.claim_scope).claimKey,digest}:{...base,action:'attest',claim_scope:proof.evidence.claim_scope,digest});
assert.equal(attestation.ok,true,`Actual attestation failed: ${stringify(attestation)}`);
const verify={...base,action:'verify',claim_key:attestation.claim_key,digest,transaction_hash:attestation.transaction_hash};
const verification=await safeCall(verify);
assert.equal(verification.status,'VERIFIED');
const changedBytes=Buffer.from(canonicalJson,'utf8');
changedBytes[Math.floor(changedBytes.length/2)]^=1;
const tamper=await safeCall({...verify,digest:sha256(changedBytes)});
assert.equal(tamper.status,'HASH_MISMATCH');
const variant=structuredClone(proof.evidence);
variant.forecast_model.version='changed-model-version-for-duplicate-test';
variant.scenario_parameters.scenario_id='changed-scenario-for-duplicate-test';
const duplicate=await safeCall({...base,action:'attest',claim_scope:variant.claim_scope,digest:sha256(Buffer.from(canonical(variant),'utf8'))});
assert.equal(duplicate.status,'REJECTED');
assert.equal(duplicate.error.code,'DUPLICATE_ACTIVE_CLAIM');
const wrongChain=await safeCall({...verify,expected_chain_id:1});
assert.equal(wrongChain.status,'UNVERIFIABLE');
assert.equal(wrongChain.error.code,'WRONG_CHAIN');
const report={created_utc:new Date().toISOString(),input_path:inputPath,evidence_id:proof.evidence_id,canonical_bytes:Buffer.byteLength(canonicalJson,'utf8'),digest,claim_scope:proof.evidence.claim_scope,revocation,attestation,verification,tamper,duplicate,wrong_chain:wrongChain};
await writeFile(new URL('../runtime/evidence-smoke.json',import.meta.url),stringify(report)+'\n');
await writeFile(new URL(`../runtime/evidence-smoke-${attestation.transaction_hash}.json`,import.meta.url),stringify(report)+'\n',{flag:'wx'});
process.stdout.write(stringify({ok:true,evidence_id:proof.evidence_id,digest,claim_key:attestation.claim_key,transaction_hash:attestation.transaction_hash,block_number:attestation.receipt.blockNumber,canonical_bytes:report.canonical_bytes,statuses:{attestation:attestation.status,verification:verification.status,tamper:tamper.status,duplicate:duplicate.status,duplicate_code:duplicate.error.code,wrong_chain:wrongChain.status},saved_report:'contracts/runtime/evidence-smoke.json'})+'\n');
