import {defineConfig} from "@playwright/test";

export default defineConfig({
  testDir: "./tests", timeout: 120000, expect: {timeout: 30000},
  fullyParallel: false, workers: 1, retries: 0,
  use: {baseURL:"http://127.0.0.1:3000",channel:process.env.GRIDPROOF_BROWSER_CHANNEL??(process.platform==="win32"?"msedge":undefined),headless:true,viewport:{width:1366,height:768},trace:"retain-on-failure"},
  reporter: [["list"]],
});
