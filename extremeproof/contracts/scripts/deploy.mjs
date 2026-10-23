// Deploy DemoToken + TriggerAgreement to the local demo chain and write
// extremeproof/.runtime/deployment.json for the providers, hub and web app.
//
// The keys are Hardhat's published development keys: they exist only on the
// local chain and must never hold real value.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createPublicClient, createWalletClient, http, maxUint256 } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { hardhat } from "viem/chains";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
const rpc = process.env.EP_RPC ?? "http://127.0.0.1:8545";

const KEYS = {
  deployer: "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
  funder: "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
  community: "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
  checker: "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
  beneficiary: "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a",
  providerStation: "0x8b3a350cf5c34c9194ca85829a2df0ec3153be0318b5e2d3348e872092edffba",
  providerEra5: "0x92db14e403b83dfe3df233f83dfa3a0d7096f21ca9b0d6d6b8d88b2b4ec1564e",
};

const artifact = (name) =>
  JSON.parse(readFileSync(join(here, "..", "artifacts", "contracts", `${name}.sol`, `${name}.json`), "utf8"));

const publicClient = createPublicClient({ chain: hardhat, transport: http(rpc) });
const nodeAccounts = (await publicClient.request({ method: "eth_accounts" })).map((a) => a.toLowerCase());
const accounts = Object.fromEntries(Object.entries(KEYS).map(([role, key]) => [role, privateKeyToAccount(key)]));
Object.values(accounts).forEach((a, i) => {
  if (nodeAccounts[i] !== a.address.toLowerCase()) throw new Error(`key ${i} does not match node account ${nodeAccounts[i]}`);
});
const wallet = (role) => createWalletClient({ account: accounts[role], chain: hardhat, transport: http(rpc) });

async function deploy(name) {
  const a = artifact(name);
  const hash = await wallet("deployer").deployContract({ abi: a.abi, bytecode: a.bytecode });
  const r = await publicClient.waitForTransactionReceipt({ hash });
  return { address: r.contractAddress, abi: a.abi };
}

const token = await deploy("DemoToken");
const escrow = await deploy("TriggerAgreement");
const send = async (role, c, functionName, args) => {
  const hash = await wallet(role).writeContract({ address: c.address, abi: c.abi, functionName, args });
  await publicClient.waitForTransactionReceipt({ hash });
};
await send("deployer", token, "mint", [accounts.funder.address, 100_000_000_00n]); // 100,000,000.00 DEMO
await send("funder", token, "approve", [escrow.address, maxUint256]);

// Snapshot right after setup: the hub's /api/reset rolls the demo chain back here (evm_revert).
const snapshot = await publicClient.request({ method: "evm_snapshot", params: [] });
const block = await publicClient.getBlock();
const out = {
  chainId: await publicClient.getChainId(),
  rpc,
  deployedAtChainTime: Number(block.timestamp),
  TriggerAgreement: escrow.address,
  DemoToken: token.address,
  roles: Object.fromEntries(Object.entries(accounts).map(([r, a]) => [r, a.address])),
  demoKeys: KEYS,
  snapshot,
  note: "Local demo chain only. Keys are Hardhat's published development keys.",
};
const dest = process.env.EP_DEPLOYMENT ?? join(root, ".runtime", "deployment.json");
mkdirSync(dirname(dest), { recursive: true });
writeFileSync(dest, JSON.stringify(out, null, 2) + "\n");
console.log(`deployed TriggerAgreement ${escrow.address}, DemoToken ${token.address} at chain time ${new Date(Number(block.timestamp) * 1000).toISOString()}`);
