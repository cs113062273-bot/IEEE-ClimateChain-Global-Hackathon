// Starts an isolated development node; deployment is explicit in this startup command.
// Never attests evidence or contacts a public network.
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdir, open, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { clients, loadDeployment, assertDeployment, projectRoot, stringify } from './chain.mjs';

const run = promisify(execFile);
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
await mkdir(new URL('../runtime/',import.meta.url),{recursive:true});
const {publicClient} = clients();
let running = false;
try {
  const chain = await publicClient.getChainId();
  if (chain !== 31337) throw new Error(`Port 8545 belongs to chain ${chain}; refusing to use it`);
  running = true;
} catch(error) {
  if (error.message?.includes('refusing')) throw error;
}
const nodeAlreadyRunning = running;
if (!running) {
  const stdout = await open(new URL('../runtime/node.stdout.log',import.meta.url),'a');
  const stderr = await open(new URL('../runtime/node.stderr.log',import.meta.url),'a');
  const cli = fileURLToPath(new URL('../node_modules/hardhat/dist/src/cli.js',import.meta.url));
  const child = spawn(process.execPath,[cli,'node','--hostname','127.0.0.1','--port','8545'],{
    cwd:projectRoot,detached:true,windowsHide:true,stdio:['ignore',stdout.fd,stderr.fd],
  });
  child.unref();
  await writeFile(new URL('../runtime/node.pid',import.meta.url),String(child.pid)+'\n');
  await stdout.close();
  await stderr.close();
  for (let attempt=0;attempt<60;attempt++) {
    await delay(500);
    try { if (await publicClient.getChainId() === 31337) {running=true;break;} } catch {}
  }
  if (!running) throw new Error('Hardhat did not start within 30s; inspect contracts/runtime/node.stderr.log');
}
let deployment;
try { deployment=await loadDeployment(); await assertDeployment(publicClient,deployment); }
catch {
  const {stdout} = await run(process.execPath,[fileURLToPath(new URL('./deploy.mjs',import.meta.url))],{cwd:projectRoot,windowsHide:true,timeout:30000});
  process.stdout.write(stdout);
  deployment=await loadDeployment();
}
process.stdout.write(stringify({ok:true,status:'AVAILABLE',chain_id:31337,contract_address:deployment.contract_address,rpc_url:'http://127.0.0.1:8545',node_already_running:nodeAlreadyRunning})+'\n');
