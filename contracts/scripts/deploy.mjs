import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { clients, artifactPath, deploymentPath, sha256, stringify, ChainError } from './chain.mjs';

const {publicClient,walletClient} = clients();
if (await publicClient.getChainId() !== 31337) throw new ChainError('WRONG_CHAIN','Deployment is restricted to local chain31337');
const artifact = JSON.parse(await readFile(artifactPath,'utf8'));
const [account] = await walletClient.getAddresses();
if (!account) throw new Error('No unlocked local development account');
const transactionHash = await walletClient.deployContract({account,abi:artifact.abi,bytecode:artifact.bytecode});
const receipt = await publicClient.waitForTransactionReceipt({hash:transactionHash});
if (receipt.status !== 'success' || !receipt.contractAddress) throw new Error('Registry deployment failed');
const code = await publicClient.getCode({address:receipt.contractAddress});
const metadata = {
  network:'LOCAL DEV CHAIN',chain_id:31337,rpc_url:'http://127.0.0.1:8545',
  contract_name:'GridProofRegistry',contract_address:receipt.contractAddress,
  deployer:account,deployment_transaction_hash:transactionHash,
  deployment_block_number:receipt.blockNumber.toString(),deployment_block_hash:receipt.blockHash,
  runtime_code_sha256:sha256(Buffer.from(code.slice(2),'hex')),
  compiled_bytecode_sha256:sha256(Buffer.from(artifact.bytecode.slice(2),'hex')),
  deployed_utc:new Date().toISOString(),compiler:'0.8.28',abi:artifact.abi,
  receipt,
};
await mkdir(new URL('../deployments/',import.meta.url),{recursive:true});
await writeFile(deploymentPath,stringify(metadata)+'\n');
process.stdout.write(stringify({...metadata,abi:undefined,receipt:undefined})+'\n');
