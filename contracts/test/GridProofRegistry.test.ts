import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { network } from 'hardhat';
import { createHash } from 'node:crypto';
import { encodeAbiParameters, keccak256, zeroHash, type Hex } from 'viem';

const digest = (text: string): Hex => ('0x' + createHash('sha256').update(text).digest('hex')) as Hex;
const site = digest('hypothetical-campus-london'), category = digest('modelled-grid-emissions-exposure');
const from = 1757635200n, to = from + 86400n;

async function setup() {
  const connection = await network.create('hardhatMainnet');
  const publicClient = await connection.viem.getPublicClient();
  const [owner, other] = await connection.viem.getWalletClients();
  const registry = await connection.viem.deployContract('GridProofRegistry');
  const key = await registry.read.computeClaimKey([site, from, to, category]);
  return {registry, publicClient, owner, other, key};
}

describe('GridProofRegistry', () => {
  it('registers the exact scope and emits a real event', async () => {
    const {registry,publicClient,owner,key} = await setup();
    assert.equal(key, keccak256(encodeAbiParameters([{type:'bytes32'},{type:'uint64'},{type:'uint64'},{type:'bytes32'}],[site,from,to,category])));
    const hash = await registry.write.registerClaim([site,from,to,category,digest('evidence-v1')]);
    const receipt = await publicClient.waitForTransactionReceipt({hash});
    assert.equal(receipt.status,'success');
    const logs = await registry.getEvents.ClaimRegistered();
    assert.equal(logs.length,1);
    assert.equal(logs[0].args.claimKey,key);
    assert.equal(logs[0].args.digest,digest('evidence-v1'));
    assert.equal(logs[0].args.submitter?.toLowerCase(),owner.account.address.toLowerCase());
    const [matches,status] = await registry.read.verifyClaim([key,digest('evidence-v1')]);
    assert.equal(matches,true);
    assert.equal(status,1);
  });

  it('rejects duplicate active evidence even when scenario and model change', async () => {
    const {registry} = await setup();
    await registry.write.registerClaim([site,from,to,category,digest(JSON.stringify({scenario_id:'campus-A',model_version:'v1'}))]);
    await assert.rejects(registry.write.registerClaim([site,from,to,category,digest(JSON.stringify({scenario_id:'campus-B',model_version:'v2'}))]),/DuplicateActiveClaim/);
  });

  it('accepts a different site, exact interval, or claim category', async () => {
    const {registry} = await setup();
    await registry.write.registerClaim([site,from,to,category,digest('first')]);
    await registry.write.registerClaim([digest('other site'),from,to,category,digest('second')]);
    await registry.write.registerClaim([site,to,to+86400n,category,digest('third')]);
    await registry.write.registerClaim([site,from,to,digest('other category'),digest('fourth')]);
    assert.equal(await registry.read.nextRecordId(),5n);
  });

  it('rejects non-owner revoke and replacement', async () => {
    const {registry,key,other} = await setup();
    await registry.write.registerClaim([site,from,to,category,digest('first')]);
    await assert.rejects(registry.write.revokeClaim([key,digest('reason')],{account:other.account}),/Unauthorized/);
    await registry.write.revokeClaim([key,digest('reason')]);
    await assert.rejects(registry.write.replaceClaim([key,digest('second')],{account:other.account}),/Unauthorized/);
  });

  it('requires revoke before explicit replacement and preserves record history', async () => {
    const {registry,key} = await setup();
    await registry.write.registerClaim([site,from,to,category,digest('first')]);
    const before = await registry.read.getRecord([1n]);
    await assert.rejects(registry.write.replaceClaim([key,digest('second')]),/RevokeBeforeReplace/);
    await registry.write.revokeClaim([key,digest('reason')]);
    assert.deepEqual((await registry.read.verifyClaim([key,digest('first')])).slice(0,2),[false,2]);
    await assert.rejects(registry.write.registerClaim([site,from,to,category,digest('second')]),/ReplacementRequired/);
    await registry.write.replaceClaim([key,digest('second')]);
    const history = await registry.read.getRecord([1n]);
    const current = await registry.read.getClaim([key]);
    assert.equal(history.digest,before.digest);
    assert.equal(history.createdAt,before.createdAt);
    assert.equal(history.submitter,before.submitter);
    assert.equal(history.status,2);
    assert.equal(history.replacedByRecordId,2n);
    assert.equal(current.previousRecordId,1n);
    assert.equal(current.status,1);
    assert.equal((await registry.getEvents.ClaimRegistered({}, {fromBlock:0n})).length,2);
    assert.equal((await registry.getEvents.ClaimRevoked({}, {fromBlock:0n})).length,1);
    assert.equal((await registry.getEvents.ClaimReplaced({}, {fromBlock:0n})).length,1);
    assert.equal((await registry.read.verifyClaim([key,digest('first')]))[0],false);
    assert.equal((await registry.read.verifyClaim([key,digest('second')]))[0],true);
  });

  it('rejects zero evidence/reason/replacement digests and invalid scopes', async () => {
    const {registry,key} = await setup();
    await assert.rejects(registry.write.registerClaim([site,from,to,category,zeroHash]),/ZeroDigest/);
    await assert.rejects(registry.write.registerClaim([zeroHash,from,to,category,digest('first')]),/InvalidScope/);
    await assert.rejects(registry.write.registerClaim([site,to,from,category,digest('first')]),/InvalidScope/);
    await assert.rejects(registry.write.registerClaim([site,from,to,zeroHash,digest('first')]),/InvalidScope/);
    await registry.write.registerClaim([site,from,to,category,digest('first')]);
    await assert.rejects(registry.write.revokeClaim([key,zeroHash]),/ZeroDigest/);
    await registry.write.revokeClaim([key,digest('reason')]);
    await assert.rejects(registry.write.replaceClaim([key,zeroHash]),/ZeroDigest/);
  });

  it('rejects one-bit tamper, wrong digest, and unknown claims', async () => {
    const {registry,key} = await setup();
    const evidence = Buffer.from('{"result":10}');
    const tampered = Buffer.from(evidence);
    tampered[tampered.length-2] ^= 1;
    await registry.write.registerClaim([site,from,to,category,digest(evidence.toString())]);
    assert.equal((await registry.read.verifyClaim([key,digest(tampered.toString())]))[0],false);
    assert.equal((await registry.read.verifyClaim([key,digest('unrelated')]))[0],false);
    assert.deepEqual((await registry.read.verifyClaim([digest('unknown'),digest('whatever')])).slice(0,2),[false,0]);
    await assert.rejects(registry.write.revokeClaim([digest('unknown'),digest('reason')]),/UnknownClaim/);
  });
});
