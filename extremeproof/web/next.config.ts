import type { NextConfig } from "next";

// EP_EDITION=static builds the public judge page into out/ (no server, no chain).
// EP_BASE_PATH serves it from a sub-path, e.g. /extremeproof on GitHub Pages.
const staticEdition = process.env.EP_EDITION === "static";
const basePath = process.env.EP_BASE_PATH ?? "";

const config: NextConfig = {
  poweredByHeader: false,
  turbopack: { root: process.cwd() },
  outputFileTracingRoot: process.cwd(),
  ...(staticEdition ? { output: "export" as const, basePath, distDir: "out-static" } : {}),
  env: { NEXT_PUBLIC_EP_EDITION: staticEdition ? "static" : "live", NEXT_PUBLIC_BASE_PATH: basePath },
};
export default config;
