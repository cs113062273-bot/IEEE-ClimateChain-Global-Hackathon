// Record the three ready-made cases from a real run of the local stack, for the
// static judge edition. Every value is read from the running UI, hub or chain;
// nothing is typed in by hand.
//
//   python -m extremeproof.scripts.stack        (repo root, in another terminal)
//   node scripts/record-runs.mjs                (extremeproof/web)
//
// Writes public/recorded/{index.json, <case>.json, <case>.zip}. Resets the
// local demo chain before each case and after the last one.
import { chromium } from "@playwright/test";
import fs from "node:fs/promises";
import crypto from "node:crypto";

const WEB = process.env.EP_BASE_URL ?? "http://127.0.0.1:3000";
const HUB = process.env.NEXT_PUBLIC_EP_HUB ?? "http://127.0.0.1:8600";
const OUT = new URL("../public/recorded/", import.meta.url);
const TAMPERS = ["spec_base_period", "observation", "evidence_outcome", "drop_evidence"];
const CASES = [
  { id: "heatwave-pays", button: /A heatwave that pays/, attack: true },
  { id: "sources-disagree", button: /Sources disagree/, attack: false },
  { id: "too-little-data", button: /Too little data/, attack: false },
];

const visible = (locator, timeout = 30000) => locator.waitFor({ state: "visible", timeout });

async function resetChain(page) {
  await page.getByRole("button", { name: "Reset demo chain" }).click();
  await visible(page.getByText(/Demo chain rolled back to 1 May 2021/));
}

async function record(page, c) {
  await page.goto(WEB);
  await resetChain(page);
  await page.locator(".case", { hasText: c.button }).click();
  await visible(page.getByText("your browser computed the same fingerprint"));
  await page.getByRole("button", { name: "Fund proposes it on chain" }).click();
  await visible(page.getByText("✓ contract terms match the signed text"));
  for (const party of ["Relief fund", "Farmers' cooperative", "Independent checker"]) {
    const card = page.locator(".party", { hasText: party });
    await card.getByRole("button").click();
    await visible(card.getByText("✓ signed"));
  }
  await page.getByRole("button", { name: /Play summer/ }).click();
  await page.getByRole("button", { name: /During the season: release as the heat builds/ }).click({ timeout: 60000 });
  await visible(page.getByText(/Released .* in the middle of the season|nothing was released early/).first());
  await page.getByRole("button", { name: /Providers fetch the season data and report/ }).click({ timeout: 60000 });
  await visible(page.getByText(/provider fetched .* and posted/).first());
  if (c.attack) {
    await page.getByRole("button", { name: /Attack: ERA5 provider lowers the signed hot line/ }).click();
    await visible(page.getByText(/rejected by the contract \(NormalMismatch\)/).first());
  }
  await page.getByRole("button", { name: /3 · Settle/ }).click();
  await visible(page.getByText(/^Settled/));
  // The dispute card appears once the agreement status refreshes; wait for it rather than sampling once.
  if ((await page.getByText(/^Settled/).first().innerText()).includes("dispute")) {
    await visible(page.getByText("Disputed — the providers did not both agree"));
    await page.getByRole("button", { name: /apply the signed fallback/ }).click();
    await visible(page.getByText(/signed fallback applied/));
  }
  // The contract refuses a rule changed after locking; read its answer from the page.
  await page.getByRole("button", { name: "Try it" }).nth(0).click();
  await visible(page.getByText(/refused · WrongStatus/));
  const contractRefusal = (await page.getByText(/refused · WrongStatus/).first().innerText()).trim();

  const log = await page.locator("ol.log li").evaluateAll((items) =>
    items.map((li) => ({
      date: li.querySelector(".t")?.textContent ?? "",
      text: li.querySelector(".what")?.textContent ?? "",
      ...(li.dataset.tx ? { tx: { hash: li.dataset.tx, block: Number(li.dataset.block), gas: Number(li.dataset.gas), events: (li.dataset.events ?? "").split(",").filter(Boolean) } } : {}),
    })));
  const bundleHref = await page.locator('a[href*="/api/bundle/"]').first().getAttribute("href");
  const aid = Number(bundleHref.split("/").pop());

  const zip = Buffer.from(await (await page.request.get(`${HUB}/api/bundle/${aid}`)).body());
  const verify = async (kind, live) =>
    (await page.request.post(`${HUB}/api/verify/${aid}?tamper_kind=${kind}&live=${live}`)).json();
  const honest = await verify("none", true);
  const offline = await verify("none", false);
  const tampered = [];
  for (const kind of TAMPERS) {
    const r = await verify(kind, true);
    tampered.push({ kind, what: r.what_was_changed, passed: r.passed, failed: r.checks.filter((x) => !x.ok).map((x) => x.check) });
  }
  // The signed text sits in a collapsed <details>, so read textContent rather than innerText.
  const spec = JSON.parse(await page.locator("pre").filter({ hasText: '"schema": "extremeproof.trigger.v2"' }).first().textContent());
  const sha256 = crypto.createHash("sha256").update(zip).digest("hex");
  await fs.writeFile(new URL(`${c.id}.zip`, OUT), zip);
  const result = {
    id: c.id, agreement: aid, spec, log, contractRefusal,
    status: (await page.locator("#replay").getByText(/^Settled/).first().innerText()).trim(),
    outcome: [...log].reverse().find((l) => /paid to|fallback applied/.test(l.text))?.text ?? null,
    verifier: { live: honest, offline }, tampered,
    bundle: { file: `${c.id}.zip`, sha256, bytes: zip.length },
  };
  await fs.writeFile(new URL(`${c.id}.json`, OUT), JSON.stringify(result, null, 1));
  console.log(c.id, "agreement", aid, "|", result.status, "| live", honest.passed, "| offline", offline.passed,
    "| tampered all fail:", tampered.every((t) => !t.passed));
  return result;
}

await fs.mkdir(OUT, { recursive: true });
// Judges download the verifier next to the bundles; it is the same standalone file as in the repository.
await fs.copyFile(new URL("../../verifier/verify.py", import.meta.url), new URL("verify.py", OUT));
const browser = await chromium.launch({ channel: process.env.EP_BROWSER_CHANNEL ?? (process.platform === "win32" ? "msedge" : undefined) });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(60000);
const deployment = await (await page.request.get(`${HUB}/api/deployment`)).json();
const runs = [];
for (const c of CASES) runs.push(await record(page, c));
await page.goto(WEB);
await resetChain(page);
await browser.close();
await fs.writeFile(new URL("index.json", OUT), JSON.stringify({
  schema: "extremeproof.recorded-runs.v1",
  recorded_at: new Date().toISOString(),
  chain: { id: deployment.chainId, contract: deployment.TriggerAgreement, token: deployment.DemoToken, note: "Local Hardhat chain; the clock is moved forward to replay past summers." },
  cases: runs.map((r) => ({ id: r.id, agreement: r.agreement, title: r.spec.title, outcome: r.outcome, bundle: r.bundle })),
}, null, 1));
console.log("wrote", runs.length, "recorded runs");
