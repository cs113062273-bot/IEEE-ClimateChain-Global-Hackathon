import { createHash } from 'node:crypto';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { createPublicClient, createWalletClient, http, keccak256, encodeAbiParameters, decodeEventLog } from 'viem';
import { hardhat, sepolia } from 'viem/chains';

export const projectRoot = fileURLToPath(new URL('../', import.meta.url));
export const workspaceRoot = fileURLToPath(new URL('../../', import.meta.url));
export const deploymentPath = new URL('../deployments/local.json', import.meta.url);
export const artifactPath = new URL('../artifacts/contracts/GridProofRegistry.sol/GridProofRegistry.json', import.meta.url);
export const stringify = value => JSON.stringify(value, (_, item) => typeof item === 'bigint' ? item.toString() : item, 2);
export const sha256 = bytes => '0x' + createHash('sha256').update(bytes).digest('hex');

export class ChainError extends Error {
  constructor(code, message, details = {}) { super(message); this.code = code; this.details = details; }
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

export function networkSettings(network = 'local') {
  if (network === 'local') return {network, chain:hardhat, chainId:31337, label:'LOCAL DEV CHAIN', confirmations:1};
  if (network === 'testnet') return {network, chain:sepolia, chainId:11155111, label:'SEPOLIA TESTNET', confirmations:2};
  throw new ChainError('UNSUPPORTED_NETWORK', 'Only local development and Sepolia testnet configurations are supported');
}

export function rpcUrl(network = 'local') {
  networkSettings(network);
  const url = network === 'local' ? (process.env.GRIDPROOF_LOCAL_RPC_URL ?? 'http://127.0.0.1:8545') : process.env.GRIDPROOF_SEPOLIA_RPC_URL;
  if (!url) throw new ChainError('NOT_CONFIGURED', 'Sepolia RPC is not configured; no public deployment is claimed');
  let parsed;
  try { parsed = new URL(url); } catch { throw new ChainError('INVALID_RPC', 'RPC URL is invalid'); }
  if (network === 'testnet') {
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password || ['localhost','127.0.0.1','[::1]'].includes(parsed.hostname)) {
      throw new ChainError('INVALID_RPC', 'Sepolia requires an operator-configured HTTPS RPC without URL userinfo');
    }
    return url;
  }
  if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname) || parsed.username || parsed.password) {
    throw new ChainError('INVALID_RPC', 'This demo bridge accepts only HTTP loopback RPC URLs');
  }
  return url;
}

export function clients(network = 'local') {
  const settings = networkSettings(network);
  const transport = http(rpcUrl(network), {timeout: 5000, retryCount: network === 'testnet' ? 1 : 0});
  return {
    publicClient: createPublicClient({chain: settings.chain, transport}),
    // Public verification never constructs a wallet or reads signer secrets.
    ...(network === 'local' ? {walletClient:createWalletClient({chain:hardhat,transport})} : {}),
  };
}

export async function loadDeployment(network = 'local') {
  const settings=networkSettings(network);
  const path=network==='local'?deploymentPath:resolve(workspaceRoot,process.env.GRIDPROOF_SEPOLIA_DEPLOYMENT_FILE??'contracts/public/sepolia-registry.json');
  let metadata;
  try { metadata=JSON.parse(await readFile(path,'utf8')); }
  catch { throw new ChainError('NOT_DEPLOYED', network==='local'?'No local deployment metadata; start the node, build, and explicitly deploy locally':'No trusted Sepolia deployment metadata; deployment requires separate authorization'); }
  if (metadata.chain_id!==settings.chainId || !/^0x[0-9a-fA-F]{40}$/.test(metadata.contract_address??'') || !Array.isArray(metadata.abi)) throw new ChainError('INVALID_METADATA','Deployment metadata is incomplete or belongs to another network');
  return metadata;
}

export async function assertDeployment(client, metadata, expected = metadata.chain_id) {
  const settings=networkSettings(metadata.chain_id===31337?'local':metadata.chain_id===11155111?'testnet':'unsupported');
  const chainId = await client.getChainId();
  if (chainId !== settings.chainId || Number(expected) !== settings.chainId || metadata.chain_id !== chainId) {
    throw new ChainError('WRONG_CHAIN', `Expected ${settings.network==='local'?'local chain 31337':'Sepolia chain 11155111'}; request expects ${expected}, RPC reports ${chainId}`);
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
  if (settings.confirmations>1 && (await client.getBlockNumber()) < receipt.blockNumber+BigInt(settings.confirmations-1)) throw new ChainError('INSUFFICIENT_CONFIRMATIONS','Sepolia deployment has fewer than two confirmations');
}

export function baseResult(metadata, claimKey) {
  const settings=networkSettings(metadata.chain_id===31337?'local':'testnet');
  return {
    network: settings.label, chain_id: settings.chainId,
    contract_address: metadata.contract_address,
    ...(claimKey ? {claim_key: claimKey} : {}),
    ...(settings.network==='testnet'?{explorer_contract_url:`https://sepolia.etherscan.io/address/${metadata.contract_address}`} : {}),
    trust_boundary: 'Integrity and exact-scope registry status only; no meter truth or carbon certification. Local chain can reset; Sepolia is a testnet.',
  };
}

// These are the current getClaim fields, not a computed revision number or
// an independently fetched complete history. Zero IDs mean no linked record.
function recordHistory(record) {
  return {
    previous_record_id: record.previousRecordId == null ? null : String(record.previousRecordId),
    replaced_by_record_id: record.replacedByRecordId == null ? null : String(record.replacedByRecordId),
    revoked_at_unix: record.revokedAt == null ? null : Number(record.revokedAt),
    reason_digest: record.reasonDigest ?? null,
  };
}

export async function verifyWithClient(client, metadata, request) {
  await assertDeployment(client, metadata, request.expected_chain_id ?? metadata.chain_id);
  const key = request.claim_key ? bytes32(request.claim_key, 'claim_key') : computeScope(request.claim_scope ?? request.scope).claimKey;
  const digest = bytes32(request.digest);
  const record = await client.readContract({address: metadata.contract_address, abi: metadata.abi, functionName:'getClaim', args:[key]});
  const result = {...baseResult(metadata, key), digest, onchain_digest: record.digest, submitter:record.submitter, created_at_unix:Number(record.createdAt), record_status:Number(record.status),record_history:recordHistory(record)};
  if (Number(record.status) === 0) return {...result, ok:false, status:'NOT_REGISTERED'};
  if (Number(record.status) === 2) return {...result, ok:false, status:'REVOKED', reason_digest:record.reasonDigest};
  if (record.digest.toLowerCase() !== digest) return {...result, ok:false, status:'HASH_MISMATCH'};
  const recordId = await client.readContract({address:metadata.contract_address, abi:metadata.abi, functionName:'latestRecordForScope', args:[key]});
  let log, receipt;
  if (metadata.chain_id===11155111) {
    if (!request.transaction_hash) throw new ChainError('REGISTRATION_TX_REQUIRED','Sepolia verification requires the actual registration transaction hash or a configured fixed proof');
    const hash=bytes32(request.transaction_hash,'transaction_hash');
    receipt=await client.getTransactionReceipt({hash});
    for (const item of receipt.logs??[]) {
      if (item.address.toLowerCase()!==metadata.contract_address.toLowerCase()) continue;
      try {
        const decoded=decodeEventLog({abi:metadata.abi,data:item.data,topics:item.topics});
        if (decoded.eventName==='ClaimRegistered' && decoded.args.claimKey===key && decoded.args.recordId===recordId && decoded.args.digest.toLowerCase()===digest && decoded.args.submitter.toLowerCase()===record.submitter.toLowerCase()) {
          log={...item,args:decoded.args,transactionHash:hash,blockNumber:receipt.blockNumber,blockHash:receipt.blockHash};break;
        }
      } catch {}
    }
  } else {
    const registeredEvent = metadata.abi.find(item => item.type === 'event' && item.name === 'ClaimRegistered');
    const logs = await client.getLogs({address:metadata.contract_address,event:registeredEvent,args:{claimKey:key},fromBlock:BigInt(metadata.deployment_block_number),toBlock:'latest'});
    log = logs.find(item => item.args.recordId === recordId && item.args.digest?.toLowerCase() === digest && item.args.submitter?.toLowerCase() === record.submitter.toLowerCase());
  }
  if (!log) throw new ChainError('MISSING_EVENT', 'No matching ClaimRegistered event for the current active record');
  if (request.transaction_hash && request.transaction_hash.toLowerCase() !== log.transactionHash.toLowerCase()) {
    throw new ChainError('TRANSACTION_MISMATCH', 'Supplied transaction does not match the current active registration event');
  }
  receipt ??= await client.getTransactionReceipt({hash: log.transactionHash});
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
  if (metadata.chain_id===11155111 && (await client.getBlockNumber()) < receipt.blockNumber+1n) throw new ChainError('INSUFFICIENT_CONFIRMATIONS','Sepolia registration has fewer than two confirmations');
  return {...result,ok:true,status:'VERIFIED',record_id:recordId,transaction_hash:log.transactionHash,...(metadata.chain_id===11155111?{explorer_transaction_url:`https://sepolia.etherscan.io/tx/${log.transactionHash}`} : {}),receipt,event:{name:'ClaimRegistered',args:decoded.args,block_number:log.blockNumber,block_hash:log.blockHash,log_index:log.logIndex}};
}

export async function loadFixedProof(network='testnet') {
  const settings=networkSettings(network);
  const path=resolve(workspaceRoot,process.env.GRIDPROOF_PUBLIC_PROOF_FILE??'contracts/public/fixed-proof.json');
  let proof;
  try {proof=JSON.parse(await readFile(path,'utf8'));} catch {throw new ChainError('FIXED_PROOF_UNAVAILABLE','No configured fixed public proof exists; no public registration is claimed');}
  return validateFixedProof(proof,network);
}

export function validateFixedProof(proof,network='testnet') {
  const settings=networkSettings(network);
  if (!proof || proof.schema_version!=='gridproof-public-proof-index/v1' || proof.network!==network || proof.chain_id!==settings.chainId) throw new ChainError('INVALID_FIXED_PROOF','Fixed proof schema/network/chain is invalid');
  bytes32(proof.claim_key,'claim_key');bytes32(proof.digest);bytes32(proof.transaction_hash,'transaction_hash');
  return proof;
}

export async function lookupWithClient(client,metadata,request) {
  await assertDeployment(client,metadata,request.expected_chain_id??metadata.chain_id);
  const key=request.claim_key?bytes32(request.claim_key,'claim_key'):computeScope(request.claim_scope??request.scope).claimKey;
  const record=await client.readContract({address:metadata.contract_address,abi:metadata.abi,functionName:'getClaim',args:[key]});
  if (Number(record.status)===0) return {...baseResult(metadata,key),ok:false,status:'NOT_REGISTERED',record_history:recordHistory(record)};
  if (Number(record.status)===2) return {...baseResult(metadata,key),ok:false,status:'REVOKED',onchain_digest:record.digest,reason_digest:record.reasonDigest,record_history:recordHistory(record)};
  const verified=await verifyWithClient(client,metadata,{...request,claim_key:key,digest:record.digest});
  return {...verified,verification_subject:'existing registry record; does not authenticate a newly supplied report digest'};
}

export async function duplicateClaimError(client,metadata,key,existing,requestedDigest) {
  let current;
  try {current=await lookupWithClient(client,metadata,{claim_key:key,expected_chain_id:metadata.chain_id});} catch(error) {current=errorResult(error,'lookup',metadata.chain_id===31337?'local':'testnet');}
  return new ChainError('DUPLICATE_ACTIVE_CLAIM','An active claim already covers this site/time/category; model or scenario changes do not alter the scope',{claim_key:key,existing_claim:current,requested_digest_matches_existing:existing.digest.toLowerCase()===bytes32(requestedDigest)});
}

export async function executeRequest(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) throw new ChainError('INVALID_INPUT', 'Request must be a JSON object');
  const network=request.network??process.env.GRIDPROOF_CHAIN_NETWORK??'local';
  const settings=networkSettings(network);
  const operation = request.action ?? request.operation;
  if (operation==='fixed-proof' && ['claim_key','digest','transaction_hash','claim_scope','scope'].some(field=>Object.hasOwn(request,field))) throw new ChainError('INVALID_INPUT','Fixed-proof mode accepts no caller-supplied replacement tuple');
  if (operation==='fixed-proof' && request.expected_chain_id!==undefined && Number(request.expected_chain_id)!==settings.chainId) throw new ChainError('WRONG_CHAIN','Expected chain conflicts with the fixed proof network');
  if (process.env.GRIDPROOF_READ_ONLY==='1' && ['attest','revoke','replace','deploy'].includes(operation)) throw new ChainError('READ_ONLY_SERVICE','This service is configured read-only; signing and registry writes are disabled');
  if (network==='testnet' && ['attest','revoke','replace','deploy'].includes(operation)) throw new ChainError('READ_ONLY_PUBLIC_CHAIN','Public bridge is read-only. No signer, deployment or public-chain write is available through this interface');
  if (operation==='config') {
    let metadata, fixed;
    try {metadata=await loadDeployment(network);} catch {}
    try {fixed=await loadFixedProof(network);} catch {}
    return {ok:true,status:'CONFIGURATION',network:settings.label,chain_id:settings.chainId,read_only:network==='testnet'||process.env.GRIDPROOF_READ_ONLY==='1',registry_address:metadata?.contract_address??null,explorer_base_url:network==='testnet'?'https://sepolia.etherscan.io':null,rpc_configured:network==='local'||Boolean(process.env.GRIDPROOF_SEPOLIA_RPC_URL),deployment_configured:Boolean(metadata),fixed_proof_configured:Boolean(fixed)};
  }
  const {publicClient, walletClient} = clients(network);
  const metadata = await loadDeployment(network);
  if (network==='testnet' && ['verify','lookup'].includes(operation) && !request.transaction_hash) {
    try {const fixed=await loadFixedProof(network);if (fixed.claim_key===request.claim_key || fixed.claim_key===computeScope(request.claim_scope??request.scope).claimKey) request={...request,transaction_hash:fixed.transaction_hash};} catch {}
  }
  if (operation==='fixed-proof') {
    const fixed=await loadFixedProof(network);
    const verified=await verifyWithClient(publicClient,metadata,{...fixed,expected_chain_id:settings.chainId});
    return {...verified,fixed_proof:fixed,read_only:true};
  }
  if (operation === 'verify') return verifyWithClient(publicClient, metadata, request);
  if (operation === 'lookup') return lookupWithClient(publicClient,metadata,request);
  await assertDeployment(publicClient, metadata, request.expected_chain_id ?? settings.chainId);
  if (operation === 'health') return {...baseResult(metadata),ok:true,status:'AVAILABLE',...(network==='local'?{rpc_url:rpcUrl()} : {}),read_only:network==='testnet',block_number:await publicClient.getBlockNumber()};
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
    if (Number(existing.status) === 1) {
      throw await duplicateClaimError(publicClient,metadata,key,existing,request.digest);
    }
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

export function errorResult(error, operation, network='local') {
  const revert = error.walk?.(cause => cause.name === 'ContractFunctionRevertedError');
  const revertCodes = {Unauthorized:'UNAUTHORIZED',ZeroDigest:'ZERO_DIGEST',InvalidScope:'INVALID_SCOPE',DuplicateActiveClaim:'DUPLICATE_ACTIVE_CLAIM',ReplacementRequired:'REPLACEMENT_REQUIRED',RevokeBeforeReplace:'REVOKE_BEFORE_REPLACE',UnknownClaim:'UNKNOWN_CLAIM',ClaimNotActive:'CLAIM_NOT_ACTIVE'};
  const code = error instanceof ChainError ? error.code : revertCodes[revert?.data?.errorName] ?? 'RPC_OR_CONTRACT_FAILURE';
  const message = error instanceof ChainError ? error.message : network==='testnet'?'Read-only Sepolia RPC or contract check failed; inspect operator configuration':(error.shortMessage ?? error.message ?? 'Chain request failed');
  const writeRejected = ['attest','revoke','replace','deploy'].includes(operation) && ['INVALID_INPUT','UNSUPPORTED_NETWORK','READ_ONLY_SERVICE','READ_ONLY_PUBLIC_CHAIN','UNAUTHORIZED','ZERO_DIGEST','INVALID_SCOPE','DUPLICATE_ACTIVE_CLAIM','REPLACEMENT_REQUIRED','REVOKE_BEFORE_REPLACE','UNKNOWN_CLAIM','CLAIM_NOT_ACTIVE'].includes(code);
  return {ok:false,status:writeRejected?'REJECTED':'UNVERIFIABLE',network:network==='testnet'?'SEPOLIA TESTNET':'LOCAL DEV CHAIN',error:{code,message},...(error instanceof ChainError?error.details:{})};
}
