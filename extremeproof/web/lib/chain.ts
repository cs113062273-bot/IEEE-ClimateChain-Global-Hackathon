// Talking to the local demo chain, the hub and the two provider services.
// Party wallets use Hardhat's published development keys; they exist only on
// the local chain started by scripts/stack.py.
import { createPublicClient, createWalletClient, decodeEventLog, http, type Abi, type Address, type Hex, type TransactionReceipt } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { hardhat } from "viem/chains";

export const HUB = process.env.NEXT_PUBLIC_EP_HUB ?? "http://127.0.0.1:8600";
export const RPC = process.env.NEXT_PUBLIC_EP_RPC ?? "http://127.0.0.1:8545";
export const STATUS = ["None", "Proposed", "Locked", "Disputed", "Paid", "Refunded", "Cancelled"] as const;
export type Status = (typeof STATUS)[number];
export type Role = "funder" | "community" | "checker" | "beneficiary";

export interface Deployment {
  chainId: number;
  TriggerAgreement: Address;
  DemoToken: Address;
  roles: Record<string, Address>;
  demoKeys: Record<string, Hex>;
  abi: { TriggerAgreement: Abi; DemoToken: Abi };
  providers: { url: string; source: "station" | "era5"; address: Address; error?: string }[];
}

export const publicClient = createPublicClient({ chain: hardhat, transport: http(RPC) });

export async function hub<T = any>(path: string, body?: unknown, method = body === undefined ? "GET" : "POST"): Promise<T> {
  const r = await fetch(HUB + path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail ?? `${r.status} ${r.statusText}`);
  return j as T;
}

export async function call<T = any>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail ?? `${r.status}`);
  return j as T;
}

export function wallet(dep: Deployment, role: string) {
  return createWalletClient({ account: privateKeyToAccount(dep.demoKeys[role]), chain: hardhat, transport: http(RPC) });
}

export async function write(dep: Deployment, role: string, functionName: string, args: readonly unknown[]) {
  const w = wallet(dep, role);
  const { request } = await publicClient.simulateContract({
    account: w.account,
    address: dep.TriggerAgreement,
    abi: dep.abi.TriggerAgreement,
    functionName,
    args,
  });
  const hash = await w.writeContract(request);
  return publicClient.waitForTransactionReceipt({ hash });
}

/** What one transaction did on chain, read from its receipt. */
export interface TxInfo {
  hash: Hex;
  block: number;
  gas: number;
  events: string[];
}

export function receiptInfo(dep: Deployment, r: TransactionReceipt): TxInfo {
  const abi = [...dep.abi.TriggerAgreement, ...dep.abi.DemoToken];
  const events = r.logs.flatMap((l) => {
    try {
      return [decodeEventLog({ abi, data: l.data, topics: l.topics }).eventName as string];
    } catch {
      return [];
    }
  });
  return { hash: r.transactionHash, block: Number(r.blockNumber), gas: Number(r.gasUsed), events };
}

/** Receipt for a transaction a provider service sent (its API returns only the hash). */
export async function txInfo(dep: Deployment, hash: string): Promise<TxInfo> {
  const h = (hash.startsWith("0x") ? hash : `0x${hash}`) as Hex;
  return receiptInfo(dep, await publicClient.waitForTransactionReceipt({ hash: h }));
}

/** Revert reason name from a viem error, e.g. "WrongStatus" or "AlreadyReported". */
export function revertName(e: unknown): string {
  const any = e as { cause?: { data?: { errorName?: string } }; shortMessage?: string; message?: string };
  let c: any = any;
  while (c) {
    if (c.data?.errorName) return c.data.errorName;
    c = c.cause;
  }
  const m = (any.shortMessage ?? any.message ?? String(e)).match(/reverted with the following reason:\s*\n?(.*)|Error: (\w+)\(/);
  return m?.[1] ?? m?.[2] ?? any.shortMessage ?? String(e);
}

export async function chainTime(): Promise<number> {
  return Number((await publicClient.getBlock()).timestamp);
}

/** Move the simulated chain clock forward (local demo chain only). */
export async function warpTo(ts: number) {
  if (ts <= (await chainTime())) return;
  await publicClient.request({ method: "evm_setNextBlockTimestamp" as any, params: [ts] as any });
  await publicClient.request({ method: "evm_mine" as any, params: [] as any });
}

export const DAY = 86400;
const ISTANBUL_OFFSET = 3 * 3600;

export function seasonTiming(year: number) {
  const start = Date.UTC(year, 5, 1) / 1000 - ISTANBUL_OFFSET;
  const end = Date.UTC(year, 9, 1) / 1000 - ISTANBUL_OFFSET;
  return { windowStart: start, windowEnd: end, reportDeadline: end + 14 * DAY, disputeWindow: 30 * DAY };
}

export async function tokenBalance(dep: Deployment, who: Address): Promise<bigint> {
  return (await publicClient.readContract({ address: dep.DemoToken, abi: dep.abi.DemoToken, functionName: "balanceOf", args: [who] })) as bigint;
}

export interface AgreementView {
  specHash: Hex;
  status: Status;
  approvals: number;
  disputeEndsAt: number;
  amount: bigint;
  quorum: number;
  onDispute: "refund" | "pay";
  token: string;
  parties: { funder: string; community: string; checker: string; beneficiary: string };
  providers: string[];
  timing: { windowStart: number; windowEnd: number; reportDeadline: number; disputeWindow: number };
  paidOut: bigint; // released to the cooperative so far
  contested: bigint; // held for the dispute
  ladder: [number, number][]; // [min days, basis points]
  limits: { seasonDays: number; maxMissing: number; maxFilled: number };
  normals: string[]; // keccak fingerprint of each provider's signed daily thresholds, in provider order
}

export async function readAgreement(dep: Deployment, id: bigint): Promise<AgreementView> {
  const a: any = await publicClient.readContract({ address: dep.TriggerAgreement, abi: dep.abi.TriggerAgreement, functionName: "getAgreement", args: [id] });
  const providers = (await publicClient.readContract({
    address: dep.TriggerAgreement,
    abi: dep.abi.TriggerAgreement,
    functionName: "providersOf",
    args: [id],
  })) as string[];
  const ladder = (await publicClient.readContract({
    address: dep.TriggerAgreement,
    abi: dep.abi.TriggerAgreement,
    functionName: "ladderOf",
    args: [id],
  })) as { minDays: number; bps: number }[];
  const normals = (await Promise.all(providers.map((p) =>
    publicClient.readContract({ address: dep.TriggerAgreement, abi: dep.abi.TriggerAgreement, functionName: "normalOf", args: [id, p] })))) as string[];
  const low = (x: string) => x.toLowerCase();
  return {
    limits: { seasonDays: Number(a.limits.seasonDays), maxMissing: Number(a.limits.maxMissing), maxFilled: Number(a.limits.maxFilled) },
    normals: normals.map(low),
    paidOut: BigInt(a.paidOut),
    contested: BigInt(a.contested),
    ladder: ladder.map((r) => [Number(r.minDays), Number(r.bps)] as [number, number]),
    specHash: a.specHash,
    status: STATUS[Number(a.status)],
    approvals: Number(a.approvals),
    disputeEndsAt: Number(a.disputeEndsAt),
    amount: BigInt(a.amount),
    quorum: Number(a.quorum),
    onDispute: Number(a.onDispute) === 1 ? "pay" : "refund",
    token: low(a.token),
    parties: { funder: low(a.parties.funder), community: low(a.parties.community), checker: low(a.parties.checker), beneficiary: low(a.parties.beneficiary) },
    providers: providers.map(low),
    timing: {
      windowStart: Number(a.timing.windowStart),
      windowEnd: Number(a.timing.windowEnd),
      reportDeadline: Number(a.timing.reportDeadline),
      disputeWindow: Number(a.timing.disputeWindow),
    },
  };
}

/** Differences between the signed settlement text and what the contract stores (empty = consistent). */
export function termMismatches(spec: any, ag: AgreementView): string[] {
  const st = spec.settlement;
  const out: string[] = [];
  if (BigInt(st.amount_cents) !== ag.amount) out.push(`amount ${st.amount_cents} vs ${ag.amount}`);
  if (st.quorum !== ag.quorum) out.push("quorum");
  if (st.on_dispute !== ag.onDispute) out.push("dispute fallback");
  if (JSON.stringify(st.payout_ladder) !== JSON.stringify(ag.ladder)) out.push("payout ladder");
  const t = st.timing;
  if (t.window_start !== ag.timing.windowStart || t.window_end !== ag.timing.windowEnd || t.report_deadline !== ag.timing.reportDeadline ||
      t.dispute_window !== ag.timing.disputeWindow) out.push("windows");
  if (st.token && st.token !== ag.token) out.push("token");
  if (st.parties && (["funder", "community", "checker", "beneficiary"] as const).some((k) => st.parties[k] !== ag.parties[k])) out.push("parties");
  if (st.provider_addresses && [st.provider_addresses.station, st.provider_addresses.era5].join() !== ag.providers.join()) out.push("providers");
  if (st.normal_keccak && [st.normal_keccak.station, st.normal_keccak.era5].join() !== ag.normals.join()) out.push("daily thresholds");
  const r = spec.rule;
  if (r.max_missing_days !== ag.limits.maxMissing || r.max_filled_days !== ag.limits.maxFilled ||
      ag.limits.seasonDays !== (t.window_end - t.window_start) / DAY) out.push("data limits");
  return out;
}

/** A provider's posted readings as the contract holds them, and the verdict it computes from them. */
export async function readReport(dep: Deployment, id: bigint, provider: Address) {
  const read = (functionName: string) =>
    publicClient.readContract({ address: dep.TriggerAgreement, abi: dep.abi.TriggerAgreement, functionName, args: [id, provider] });
  const [verdict, longestSpell] = (await read("reportOf")) as [number, number];
  const r = (await read("getRecord")) as { posted: number; longest: number; filled: number; missing: number; isFinal: boolean; dayLog: Hex };
  return { verdict: Number(verdict), longestSpell: Number(longestSpell), posted: Number(r.posted), filled: Number(r.filled),
           missing: Number(r.missing), isFinal: r.isFinal, dayLog: r.dayLog };
}

export async function sha256Bytes(buf: ArrayBuffer): Promise<Hex> {
  const d = await crypto.subtle.digest("SHA-256", buf);
  return ("0x" + Array.from(new Uint8Array(d), (b) => b.toString(16).padStart(2, "0")).join("")) as Hex;
}

/** sha256 of the canonical JSON, computed in the browser to cross-check the hub. */
export async function sha256Hex(text: string): Promise<Hex> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return ("0x" + Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("")) as Hex;
}

export function canonicalJson(v: unknown): string {
  if (v === null || typeof v !== "object") {
    if (typeof v === "number" && !Number.isInteger(v)) throw new Error("floats are not allowed in a spec");
    return JSON.stringify(v);
  }
  if (Array.isArray(v)) return "[" + v.map(canonicalJson).join(",") + "]";
  const o = v as Record<string, unknown>;
  return "{" + Object.keys(o).sort().map((k) => JSON.stringify(k) + ":" + canonicalJson(o[k])).join(",") + "}";
}

export const fmtDemo = (cents: bigint) =>
  (Number(cents) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " DEMO";

export const fmtChainDate = (ts: number) =>
  new Date((ts + ISTANBUL_OFFSET) * 1000).toISOString().slice(0, 16).replace("T", " ") + " (UTC+3)";
