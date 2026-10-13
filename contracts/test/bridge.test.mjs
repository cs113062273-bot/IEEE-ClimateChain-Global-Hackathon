import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { computeScope, sha256, assertDeployment, verifyWithClient, errorResult, ChainError } from '../scripts/chain.mjs';
import { parseAbi, encodeAbiParameters, encodeEventTopics } from 'viem';

const scope = {site_hash:sha256('campus'),from_utc:'2025-09-12T00:00:00Z',to_utc:'2025-09-13T00:00:00Z',category:'modelled-grid-emissions-exposure'};
const metadata = {chain_id:31337,contract_address:'0x'+'11'.repeat(20),runtime_code_sha256:sha256(Buffer.from('6000','hex')),deployment_transaction_hash:'0x'+'22'.repeat(32),deployment_block_number:'1',deployment_block_hash:'block1',abi:[]};
const healthy = () => ({getChainId:async()=>31337,getCode:async()=>'0x6000',getTransactionReceipt:async()=>({status:'success',contractAddress:metadata.contract_address,blockNumber:1n,blockHash:'block1'}),getBlock:async()=>({hash:'block1'})});

function registrationFixture() {
  const abi = parseAbi(['event ClaimRegistered(bytes32 indexed claimKey, uint256 indexed recordId, address indexed submitter, bytes32 digest, uint64 createdAt, uint256 previousRecordId)']);
  const key=computeScope(scope).claimKey, digest=sha256('original'), transactionHash='0x'+'33'.repeat(32);
  const args={claimKey:key,recordId:1n,submitter:metadata.contract_address,digest,createdAt:100n,previousRecordId:0n};
  const log={address:metadata.contract_address,args,transactionHash,logIndex:0,blockNumber:2n,blockHash:'block2',topics:encodeEventTopics({abi,eventName:'ClaimRegistered',args}),data:encodeAbiParameters([{type:'bytes32'},{type:'uint64'},{type:'uint256'}],[digest,100n,0n])};
  const receipt={status:'success',to:metadata.contract_address,blockNumber:2n,blockHash:'block2',logs:[log]};
  const client={...healthy(),readContract:async input=>input.functionName==='getClaim'?{digest,submitter:metadata.contract_address,createdAt:100n,status:1}:1n,getLogs:async()=>[log],getTransactionReceipt:async input=>input.hash===metadata.deployment_transaction_hash?{status:'success',contractAddress:metadata.contract_address,blockNumber:1n,blockHash:'block1'}:receipt,getBlock:async input=>({hash:input.blockNumber===1n?'block1':'block2'})};
  return {client,metadata:{...metadata,abi},request:{claim_scope:scope,digest},receipt,log,transactionHash};
}

describe('local bridge fails closed', () => {
  it('scope never depends on model or scenario IDs',()=>{
    assert.equal(computeScope(scope).claimKey,computeScope({...scope,model_version:'v2',scenario_id:'different'}).claimKey);
    assert.notEqual(computeScope(scope).claimKey,computeScope({...scope,site_hash:sha256('another campus')}).claimKey);
  });
  it('rejects impossible dates, timezone offsets, empty scope, and zero digests',()=>{
    assert.throws(()=>computeScope({...scope,from_utc:'2025-02-30T00:00:00Z'}),/Invalid scope timestamp/);
    assert.throws(()=>computeScope({...scope,from_utc:'2025-09-12T00:00:00+00:00'}),/whole-second ISO UTC/);
    assert.throws(()=>computeScope({...scope,to_utc:scope.from_utc}),/nonempty/);
    assert.throws(()=>computeScope({...scope,site_hash:'0x'+'00'.repeat(32)}),/nonzero/);
  });
  it('rejects the wrong RPC chain and wrong expected chain',async()=>{
    await assert.rejects(assertDeployment({...healthy(),getChainId:async()=>1},metadata),/Expected local chain/);
    await assert.rejects(assertDeployment(healthy(),metadata,11155111),/Expected local chain/);
  });
  it('RPC failure remains UNVERIFIABLE',async()=>{
    let failure;
    try { await assertDeployment({...healthy(),getChainId:async()=>{throw new Error('RPC connection refused');}},metadata); }
    catch(error) { failure=errorResult(error); }
    assert.equal(failure.status,'UNVERIFIABLE');
    assert.equal(failure.ok,false);
  });
  it('known rejected writes are distinct from unavailable verification',()=>{
    const duplicate=errorResult(new ChainError('DUPLICATE_ACTIVE_CLAIM','Scope already active'),'attest');
    assert.equal(duplicate.status,'REJECTED');
    assert.equal(duplicate.error.code,'DUPLICATE_ACTIVE_CLAIM');
    assert.equal(errorResult(new ChainError('INVALID_INPUT','Zero digest'),'attest').status,'REJECTED');
    assert.equal(errorResult(new ChainError('INVALID_INPUT','Missing digest'),'verify').status,'UNVERIFIABLE');
  });
  it('rejects missing bytecode and stale deployment receipts',async()=>{
    await assert.rejects(assertDeployment({...healthy(),getCode:async()=>undefined},metadata),/bytecode is missing/);
    await assert.rejects(assertDeployment({...healthy(),getBlock:async()=>({hash:'reorg'})},metadata),/no longer canonical/);
  });
  it('rejects a repeated deterministic deployment hash after a local-node reset',async()=>{
    const resetClient={...healthy(),getTransactionReceipt:async()=>({status:'success',contractAddress:metadata.contract_address,blockNumber:1n,blockHash:'newgenesisblock'}),getBlock:async()=>({hash:'newgenesisblock'})};
    await assert.rejects(assertDeployment(resetClient,metadata),/differs from the captured deployment block/);
  });
  it('does not verify digest mismatch or revoked evidence',async()=>{
    const client = {...healthy(),readContract:async()=>({digest:sha256('original'),submitter:metadata.contract_address,createdAt:1n,status:1})};
    const result = await verifyWithClient(client,metadata,{claim_scope:scope,digest:sha256('tampered')});
    assert.equal(result.status,'HASH_MISMATCH');
    assert.equal(result.ok,false);
    client.readContract=async()=>({digest:sha256('original'),submitter:metadata.contract_address,createdAt:1n,status:2,reasonDigest:sha256('reason')});
    assert.equal((await verifyWithClient(client,metadata,{claim_scope:scope,digest:sha256('original')})).status,'REVOKED');
  });
  it('rejects a matching digest when the registration event is missing',async()=>{
    const client = {...healthy(),readContract:async input=>input.functionName==='getClaim'?{digest:sha256('original'),submitter:metadata.contract_address,createdAt:1n,status:1}:1n,getLogs:async()=>[]};
    await assert.rejects(verifyWithClient(client,metadata,{claim_scope:scope,digest:sha256('original')}),/No matching ClaimRegistered event/);
  });
  it('requires scope, digest, record, event and canonical successful receipt to agree',async()=>{
    const fixture=registrationFixture();
    const result=await verifyWithClient(fixture.client,fixture.metadata,fixture.request);
    assert.equal(result.status,'VERIFIED');
    assert.equal(result.transaction_hash,fixture.transactionHash);
  });
  it('rejects an unrelated transaction hash and a reverted registration receipt',async()=>{
    const fixture=registrationFixture();
    await assert.rejects(verifyWithClient(fixture.client,fixture.metadata,{...fixture.request,transaction_hash:'0x'+'44'.repeat(32)}),/Supplied transaction does not match/);
    fixture.receipt.status='reverted';
    await assert.rejects(verifyWithClient(fixture.client,fixture.metadata,fixture.request),/not a successful call/);
  });
  it('rejects stale registration blocks and missing receipt events',async()=>{
    const fixture=registrationFixture();
    fixture.log.blockHash='reorganized';
    await assert.rejects(verifyWithClient(fixture.client,fixture.metadata,fixture.request),/no longer in the canonical chain/);
    fixture.log.blockHash='block2';
    fixture.receipt.logs=[];
    await assert.rejects(verifyWithClient(fixture.client,fixture.metadata,fixture.request),/receipt omits/);
  });
});
