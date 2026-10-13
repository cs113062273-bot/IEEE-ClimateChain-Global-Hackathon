import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { createPublicClient, createWalletClient, http, keccak256, encodeAbiParameters, decodeEventLog } from 'viem';
import { hardhat } from 'viem/chains';

export const projectRoot = fileURLToPath(new URL('../', import.meta.url));
export const deploymentPath = new URL('../deployments/local.json', import.meta.url);
export const artifactPath = new URL('../artifacts/contracts/GridProofRegistry.sol/GridProofRegistry.json', import.meta.url);
export const stringify = value => JSON.stringify(value, (_, item) => typeof item === 'bigint' ? item.toString() : item, 2);
export const sha256 = bytes => '0x' + createHash('sha256').update(bytes).digest('hex');

export class ChainError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

export function bytes32(value, label = 'digest') {
  const text = typeof value === 'string' && !value.startsWith('0x') ? '0x' + value : value;
  if (typeof text !== 'string' || !/^0x[0-9a-fA-F]{64}$/.test(text) || /^0x0{64}$/.test(text)) {
    throw new ChainError('INVALID_INPUT', `${label} must be a nonzero 32-byte hex value`);
  }
  return text.toLowerCase();
}

export function computeScope(scope) {
  if (!scope || typeof scope !== 'object') throw new ChainError('INVALID_INPUT', 'claim_scope is required');
  const siteHash = bytes32(scope.site_hash, 'site_hash');
  const timestamp = value => {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) {
      throw new ChainError('INVALID_INPUT', 'Scope timestamps must be whole-second ISO UTC ending Z');
    }
    const millis = Date.parse(value);
    if (!Number.isFinite(millis) || new Date(millis).toISOString().replace('.000Z', 'Z') !== value || millis < 0) {
      throw new ChainError('INVALID_INPUT', 'Invalid scope timestamp');
    }
    return BigInt(millis / 1000);
  };
  const fromUtc = timestamp(scope.from_utc), toUtc = timestamp(scope.to_utc);
  if (fromUtc >= toUtc) throw new ChainError('INVALID_INPUT', 'Scope must be a nonempty [from,to) interval');
  if (typeof scope.category !== 'string' || scope.category.length === 0 || scope.category.length > 128) {
    throw new ChainError('INVALID_INPUT', 'category must contain 1..128 characters');
  }
  const categoryHash = sha256(Buffer.from(scope.category, 'utf8'));
  const claimKey = keccak256(encodeAbiParameters(
    [{type:'bytes32'}, {type:'uint64'}, {type:'uint64'}, {type:'bytes32'}],
    [siteHash, fromUtc, toUtc, categoryHash],
  ));
  return {siteHash, fromUtc, toUtc, categoryHash, claimKey};
}

export function rpcUrl() {
  const url = process.env.GRIDPROOF_LOCAL_RPC_URL ?? 'http://127.0.0.1:8545';
  let parsed;
  try { parsed = new URL(url); } catch { throw new ChainError('INVALID_RPC', 'RPC URL is invalid'); }
  if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname) || parsed.username || parsed.password) {
    throw new ChainError('INVALID_RPC', 'This demo bridge accepts only HTTP loopback RPC URLs');
  }
  return url;
}

export function clients() {
  const transport = http(rpcUrl(), {timeout: 5000, retryCount: 0});
  return {
    publicClient: createPublicClient({chain: hardhat, transport}),
    walletClient: createWalletClient({chain: hardhat, transport}),
  };
}

export async function loadDeployment() {
  try { return JSON.parse(await readFile(deploymentPath, 'utf8')); }
  catch { throw new ChainError('NOT_DEPLOYED', 'No local deployment metadata; start the node, build, and run npm run deploy in contracts'); }
}

export async function assertDeployment(client, metadata, expected = 31337) {
  const chainId = await client.getChainId();
  if (chainId !== 31337 || Number(expected) !== 31337 || metadata.chain_id !== chainId) {
    throw new ChainError('WRONG_CHAIN', `Expected local chain 31337; request expects ${expected}, RPC reports ${chainId}`);
  }
  const code = await client.getCode({address: metadata.contract_address});
  if (!code || code === '0x' || sha256(Buffer.from(code.slice(2), 'hex')) !== metadata.runtime_code_sha256) {
    throw new ChainError('CONTRACT_MISMATCH', 'Registry bytecode is missing or differs from this deployment');
  }
  const receipt = await client.getTransactionReceipt({hash: metadata.deployment_transaction_hash});
  if (receipt.status !== 'success' || receipt.contractAddress?.toLowerCase() !== metadata.contract_address.toLowerCase()) {
    throw new ChainError('STALE_DEPLOYMENT', 'Deployment receipt is missing, failed, or belongs to another contract');
  }
  if (receipt.blockHash !== metadata.deployment_block_hash || receipt.blockNumber.toString() !== metadata.deployment_block_number.toString()) {
    throw new ChainError('STALE_DEPLOYMENT', 'Deployment receipt differs from the captured deployment block; the local node may have been reset');
  }
  const block = await client.getBlock({blockNumber: receipt.blockNumber});
  if (block.hash !== receipt.blockHash) throw new ChainError('STALE_DEPLOYMENT', 'Deployment block is no longer canonical');
}

export function baseResult(metadata, claimKey) {
  return {
    network: 'LOCAL DEV CHAIN', chain_id: 31337,
    contract_address: metadata.contract_address,
    ...(claimKey ? {claim_key: claimKey} : {}),
    trust_boundary: 'Integrity and exact-scope registry status only; no meter truth, carbon credit, or public-chain finality.',
  };
}

export async function verifyWithClient(client, metadata, request) {
  await assertDeployment(client, metadata, request.expected_chain_id ?? 31337);
  const key = request.claim_key ? bytes32(request.claim_key, 'claim_key') : computeScope(request.claim_scope ?? request.scope).claimKey;
  const digest = bytes32(request.digest);
  const record = await client.readContract({address: metadata.contract_address, abi: metadata.abi, functionName:'getClaim', args:[key]});
  const result = {...baseResult(metadata, key), digest, onchain_digest: record.digest, submitter:record.submitter, created_at_unix:Number(record.createdAt), record_status:Number(record.status)};
  if (Number(record.status) === 0) return {...result, ok:false, status:'NOT_REGISTERED'};
  if (Number(record.status) === 2) return {...result, ok:false, status:'REVOKED', reason_digest:record.reasonDigest};
  if (record.digest.toLowerCase() !== digest) return {...result, ok:false, status:'HASH_MISMATCH'};
  const recordId = await client.readContract({address:metadata.contract_address, abi:metadata.abi, functionName:'latestRecordForScope', args:[key]});
  const registeredEvent = metadata.abi.find(item => item.type === 'event' && item.name === 'ClaimRegistered');
  const logs = await client.getLogs({address:metadata.contract_address,event:registeredEvent,args:{claimKey:key},fromBlock:BigInt(metadata.deployment_block_number),toBlock:'latest'});
  const log = logs.find(item => item.args.recordId === recordId && item.args.digest?.toLowerCase() === digest && item.args.submitter?.toLowerCase() === record.submitter.toLowerCase());
  if (!log) throw new ChainError('MISSING_EVENT', 'No matching ClaimRegistered event for the current active record');
  if (request.transaction_hash && request.transaction_hash.toLowerCase() !== log.transactionHash.toLowerCase()) {
    throw new ChainError('TRANSACTION_MISMATCH', 'Supplied transaction does not match the current active registration event');
  }
  const receipt = await client.getTransactionReceipt({hash: log.transactionHash});
  if (receipt.status !== 'success' || receipt.to?.toLowerCase() !== metadata.contract_address.toLowerCase()) {
    throw new ChainError('FAILED_TRANSACTION', 'Registration receipt is not a successful call to the registry');
  }
  const block = await client.getBlock({blockNumber:receipt.blockNumber});
  if (block.hash !== receipt.blockHash || log.blockHash !== block.hash) throw new ChainError('STALE_TRANSACTION', 'Registration event is no longer in the canonical chain');
  const receiptLog = receipt.logs.find(item => item.address.toLowerCase() === metadata.contract_address.toLowerCase() && item.logIndex === log.logIndex);
  if (!receiptLog) throw new ChainError('MISSING_EVENT', 'Registration receipt omits the corresponding event');
  const decoded = decodeEventLog({abi:metadata.abi,data:receiptLog.data,topics:receiptLog.topics});
  if (decoded.eventName !== 'ClaimRegistered' || decoded.args.claimKey !== key || decoded.args.digest.toLowerCase() !== digest || decoded.args.recordId !== recordId) {
    throw new ChainError('MISSING_EVENT', 'Receipt event does not bind this scope and digest');
  }
  return {...result,ok:true,status:'VERIFIED',record_id:recordId,transaction_hash:log.transactionHash,receipt,event:{name:'ClaimRegistered',args:decoded.args,block_number:log.blockNumber,block_hash:log.blockHash,log_index:log.logIndex}};
}

export async function executeRequest(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) throw new ChainError('INVALID_INPUT', 'Request must be a JSON object');
  if ((request.network ?? 'local') !== 'local') throw new ChainError('UNSUPPORTED_NETWORK', 'Only the zero-cost local development chain is implemented');
  const operation = request.action ?? request.operation;
  const {publicClient, walletClient} = clients();
  const metadata = await loadDeployment();
  if (operation === 'verify') return verifyWithClient(publicClient, metadata, request);
  await assertDeployment(publicClient, metadata, request.expected_chain_id ?? 31337);
  if (operation === 'health') return {...baseResult(metadata),ok:true,status:'AVAILABLE',rpc_url:rpcUrl(),block_number:await publicClient.getBlockNumber()};
  if (!['attest','revoke','replace'].includes(operation)) throw new ChainError('INVALID_INPUT', 'Unknown bridge action');
  const addresses = await walletClient.getAddresses();
  const account = addresses.find(address => address.toLowerCase() === metadata.deployer.toLowerCase());
  if (!account) throw new ChainError('ACCOUNT_UNAVAILABLE', 'Local development submitter account is not available');
  let key, functionName, args;
  if (operation === 'attest') {
    const scope = computeScope(request.claim_scope ?? request.scope);
    key = scope.claimKey;
    functionName = 'registerClaim';
    args = [scope.siteHash, scope.fromUtc, scope.toUtc, scope.categoryHash, bytes32(request.digest)];
    const existing = await publicClient.readContract({address:metadata.contract_address,abi:metadata.abi,functionName:'getClaim',args:[key]});
    if (Number(existing.status) === 1) throw new ChainError('DUPLICATE_ACTIVE_CLAIM', 'An active claim already covers this site/time/category; model or scenario changes do not alter the scope');
    if (Number(existing.status) === 2) throw new ChainError('REPLACEMENT_REQUIRED', 'The previous claim was revoked; use an explicit authorized replace action');
  } else {
    key = bytes32(request.claim_key, 'claim_key');
    functionName = operation === 'revoke' ? 'revokeClaim' : 'replaceClaim';
    args = [key, bytes32(operation === 'revoke' ? request.reason_digest : request.digest)];
  }
  const simulation = await publicClient.simulateContract({account,address:metadata.contract_address,abi:metadata.abi,functionName,args});
  const transactionHash = await walletClient.writeContract(simulation.request);
  const receipt = await publicClient.waitForTransactionReceipt({hash:transactionHash,timeout:15000,confirmations:1});
  if (receipt.status !== 'success') throw new ChainError('FAILED_TRANSACTION', 'Local transaction reverted');
  const events = receipt.logs.filter(log => log.address.toLowerCase() === metadata.contract_address.toLowerCase()).map(log => ({...decodeEventLog({abi:metadata.abi,data:log.data,topics:log.topics}),log_index:log.logIndex}));
  const result = {...baseResult(metadata,key),ok:true,status:operation === 'revoke' ? 'REVOKED' : 'ATTESTED',digest:request.digest ? bytes32(request.digest) : undefined,transaction_hash:transactionHash,receipt,events};
  await mkdir(new URL('../runtime/receipts/',import.meta.url),{recursive:true});
  await writeFile(new URL(`../runtime/receipts/${transactionHash}.json`,import.meta.url),stringify(result)+'\n');
  return result;
}

export function errorResult(error, operation) {
  const revert = error.walk?.(cause => cause.name === 'ContractFunctionRevertedError');
  const revertCodes = {Unauthorized:'UNAUTHORIZED',ZeroDigest:'ZERO_DIGEST',InvalidScope:'INVALID_SCOPE',DuplicateActiveClaim:'DUPLICATE_ACTIVE_CLAIM',ReplacementRequired:'REPLACEMENT_REQUIRED',RevokeBeforeReplace:'REVOKE_BEFORE_REPLACE',UnknownClaim:'UNKNOWN_CLAIM',ClaimNotActive:'CLAIM_NOT_ACTIVE'};
  const code = error instanceof ChainError ? error.code : revertCodes[revert?.data?.errorName] ?? 'RPC_OR_CONTRACT_FAILURE';
  const message = error instanceof ChainError ? error.message : (error.shortMessage ?? error.message ?? 'Chain request failed');
  const writeRejected = ['attest','revoke','replace'].includes(operation) && ['INVALID_INPUT','UNSUPPORTED_NETWORK','UNAUTHORIZED','ZERO_DIGEST','INVALID_SCOPE','DUPLICATE_ACTIVE_CLAIM','REPLACEMENT_REQUIRED','REVOKE_BEFORE_REPLACE','UNKNOWN_CLAIM','CLAIM_NOT_ACTIVE'].includes(code);
  return {ok:false,status:writeRejected?'REJECTED':'UNVERIFIABLE',network:'LOCAL DEV CHAIN',error:{code,message}};
}
