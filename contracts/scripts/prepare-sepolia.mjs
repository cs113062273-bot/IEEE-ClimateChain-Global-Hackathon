import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {artifactPath,sha256,stringify,clients,ChainError} from './chain.mjs';
import {readSepoliaSigner,publicSigningIsDisabled} from './sepolia-preparation.mjs';

async function main() {
if (process.argv.includes('--broadcast') || process.argv.includes('--deploy')) publicSigningIsDisabled();
const artifact=JSON.parse(await readFile(artifactPath,'utf8'));
const plan={status:'PREPARED_NOT_DEPLOYED',network:'SEPOLIA TESTNET',chain_id:11155111,contract_name:'GridProofRegistry',compiler:'0.8.28',compiled_bytecode_sha256:sha256(Buffer.from(artifact.bytecode.slice(2),'hex')),source_sha256:sha256(await readFile(new URL('../contracts/GridProofRegistry.sol',import.meta.url))),signer_address:null,rpc_checked:false,public_writes_available:false,authorization_required:['public deployment','registration of the reviewed fixed evidence digest'],created_utc:new Date().toISOString()};
if (process.argv.includes('--signer')) plan.signer_address=readSepoliaSigner().address;
if (process.argv.includes('--rpc')) {
  const client=clients('testnet').publicClient;
  const chainId=await client.getChainId();
  if (chainId!==11155111) throw new ChainError('WRONG_CHAIN','Configured RPC is not Sepolia chain 11155111');
  plan.rpc_checked=true;
  plan.rpc_block_number=(await client.getBlockNumber()).toString();
  if (plan.signer_address) plan.signer_balance_wei=(await client.getBalance({address:plan.signer_address})).toString();
}
await mkdir(new URL('../runtime/',import.meta.url),{recursive:true});
await writeFile(new URL('../runtime/sepolia-deployment-plan.json',import.meta.url),stringify(plan)+'\n');
process.stdout.write(stringify(plan)+'\n');
}
main().catch(error=>{
  process.stderr.write(stringify({ok:false,status:'PREPARATION_FAILED',error:{code:error instanceof ChainError?error.code:'RPC_OR_BUILD_FAILURE',message:error instanceof ChainError?error.message:'Read-only preparation failed; check local build and operator RPC configuration'}})+'\n');
  process.exitCode=1;
});
