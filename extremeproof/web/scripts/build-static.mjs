// Build the public static edition into out-static/, then rebuild the live
// edition: next build always rewrites .next, which `next start` serves.
//
//   node scripts/build-static.mjs                    (served from the site root)
//   EP_BASE_PATH=/extremeproof node scripts/build-static.mjs
//
// Run scripts/record-runs.mjs first so public/recorded/ holds current runs.
import { spawnSync } from "node:child_process";
import fs from "node:fs";

const next = (env) => {
  const r = spawnSync(process.platform === "win32" ? "npx.cmd" : "npx", ["next", "build"], { stdio: "inherit", shell: process.platform === "win32", env: { ...process.env, ...env } });
  if (r.status !== 0) process.exit(r.status ?? 1);
};

for (const f of ["index.json", "verify.py", "heatwave-pays.zip", "sources-disagree.zip", "too-little-data.zip"]) {
  if (!fs.existsSync(new URL(`../public/recorded/${f}`, import.meta.url))) {
    console.error(`public/recorded/${f} is missing: run scripts/record-runs.mjs against the live stack first.`);
    process.exit(1);
  }
}
next({ EP_EDITION: "static" });
next({ EP_EDITION: "live" });
console.log("static edition in out-static/; live build restored in .next/ (restart `next start` to serve it)");
