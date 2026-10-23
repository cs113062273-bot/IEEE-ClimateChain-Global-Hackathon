// The live edition talks to the local chain, hub and providers. The static
// edition (EP_EDITION=static npm run build) is a public page with no backend:
// the rule comparison runs in the browser and steps 3–6 show recorded runs.
export const STATIC_EDITION = process.env.NEXT_PUBLIC_EP_EDITION === "static";

// Prefix for files under public/ when the static page is served from a sub-path.
export const asset = (path: string) => `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}${path}`;
