import { defineConfig } from "hardhat/config";
import hardhatViem from "@nomicfoundation/hardhat-viem";
import hardhatNodeTestRunner from "@nomicfoundation/hardhat-node-test-runner";

// Local chain only. The demo node starts on a simulated date (EXTREMEPROOF_CHAIN_START,
// ISO date) so a past season can be replayed with the "lock before the season" rule enforced.
const start = process.env.EXTREMEPROOF_CHAIN_START;

export default defineConfig({
  plugins: [hardhatViem, hardhatNodeTestRunner],
  solidity: {
    version: "0.8.28",
    preferWasm: true,
    settings: { optimizer: { enabled: true, runs: 200 }, viaIR: true, evmVersion: "cancun" },
  },
  networks: {
    hardhatMainnet: {
      type: "edr-simulated",
      chainType: "l1",
      chainId: 31337,
      ...(start ? { initialDate: new Date(start) } : {}),
    },
    localhost: { type: "http", chainType: "l1", url: "http://127.0.0.1:8545", chainId: 31337 },
  },
});
