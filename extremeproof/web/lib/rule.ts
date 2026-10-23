// Backtest logic over the precomputed tables in public/data/<site>.json.
// The heavy statistics (percentiles, bootstrap replicates, gap filling) are
// computed in Python by the cross-validated engine; here we only apply the
// rule's integer settings (minimum spell, data limits) to those results.

export type Base = "1961-1990" | "1991-2020";
export type VariantId = "era5" | "station" | "station_qm" | "station_linear" | "station_raw";

export interface BacktestRow {
  missing: number;
  filled: number;
  longest?: number;
  reps?: number[];
}

export interface SiteData {
  site: { id: string; name: string; station: string; blurb: string };
  station: { id: string; lat: number; lon: number; elev_m: number; qc_excluded: number };
  era5_grid: { lat: number; lon: number; elev_m: number };
  series: { start: string; station: (number | null)[]; era5: (number | null)[] };
  coverage: Record<"station" | "era5", Record<Base, number>>;
  thresholds: Record<string, (number | null)[]>;
  backtest: Record<string, Record<string, BacktestRow>>;
  years: number[];
  notes: Record<string, string>;
}

export const VARIANTS: { id: VariantId; source: "station" | "era5"; fill: string; label: string; short: string }[] = [
  { id: "era5", source: "era5", fill: "none", label: "ERA5 reanalysis", short: "ERA5" },
  { id: "station", source: "station", fill: "none", label: "Station, gaps left empty", short: "Station" },
  { id: "station_qm", source: "station", fill: "era5_quantile_map", label: "Station + quantile-mapped ERA5 fill", short: "Stn + QM" },
  { id: "station_linear", source: "station", fill: "era5_monthly_linear", label: "Station + linear-corrected ERA5 fill", short: "Stn + linear" },
  { id: "station_raw", source: "station", fill: "era5_raw", label: "Station + raw ERA5 fill", short: "Stn + raw" },
];

export const MIN_BASE_COVERAGE = 600; // per mille, as in the spec

export interface Rule {
  variant: VariantId; // provider A's data: always a station variant (provider B is always ERA5)
  base: Base;
  percentile: 90 | 95;
  minSpell: number;
  maxMissing: number;
  maxFilled: number;
  onDispute: "refund" | "pay";
  payout?: "flat" | "graded"; // all or nothing at minSpell, or graded by spell length (default flat)
  steps?: [number, number][]; // graded rungs: [days beyond minSpell, basis points]; default GRADED_STEPS
}

/** Spell length -> share of the deposit in basis points; the signed spec and the contract hold the same ladder. */
export type Ladder = [number, number][];
export const GRADED_STEPS: [number, number][] = [[0, 4000], [3, 7000], [6, 10000]];
export function ladderOf(rule: Rule): Ladder {
  return rule.payout === "graded" ? (rule.steps ?? GRADED_STEPS).map(([d, bps]) => [rule.minSpell + d, bps]) : [[rule.minSpell, 10000]];
}
export function shareOf(ladder: Ladder, spell: number) {
  let bps = 0;
  for (const [days, b] of ladder) if (spell >= days) bps = b;
  return bps / 10000;
}
export const ladderText = (l: Ladder) =>
  l.length === 1 ? `all at ${l[0][0]}+ days` : l.map(([d, b]) => `${b / 100}% at ${d}+ days`).join(", ");

export type Outcome = "pay" | "refund" | "dispute";

/**
 * What the 2-of-2 agreement would do. The share both providers support is paid at once, the share
 * neither supports is returned at once, and only the difference is disputed (all of it when a
 * provider has no verdict). With an all-or-nothing ladder this is: both met -> pay, both not -> refund.
 */
export function agreementOutcome(d: SiteData, rule: Rule, year: number) {
  const a = verdict(d, rule, year);
  const b = verdict(d, { ...rule, variant: "era5" }, year);
  const split = settle([a, b], ladderOf(rule));
  const outcome: Outcome = split.contested > 0 ? "dispute" : split.payNow > 0 ? "pay" : "refund";
  return { outcome, a, b, ...split };
}

/** Shares of the deposit (0..1): paid at once, returned at once, contested. */
export function settle(vs: Verdict[], ladder: Ladder) {
  if (vs.some((v) => v.state === "nodata")) return { payNow: 0, refundNow: 0, contested: 1 };
  const shares = vs.map((v) => shareOf(ladder, v.payoutSpell ?? v.longest ?? 0)).sort((x, y) => x - y);
  const payNow = shares[0];
  const owedAtMost = shares[shares.length - 1];
  return { payNow, refundNow: 1 - owedAtMost, contested: owedAtMost - payNow };
}

export type State = "met" | "not" | "nodata";

export interface Verdict {
  state: State;
  longest: number | null; // mean over replicates for in-base years
  share?: number; // fraction of bootstrap replicates that trigger
  // In-base years: the median bootstrap replicate. With 29 replicates, median >= minSpell exactly when at
  // least half the replicates trigger, so an all-or-nothing ladder gives the same verdict as "share".
  payoutSpell?: number;
  missing: number;
  filled: number;
  inBase: boolean;
  why?: string;
}

export function inBase(year: number, base: Base) {
  const [a, b] = base.split("-").map(Number);
  return year >= a && year <= b;
}

export function verdict(d: SiteData, rule: Rule, year: number): Verdict {
  const v = VARIANTS.find((x) => x.id === rule.variant)!;
  const row = d.backtest[`${rule.variant}|${rule.base}|${rule.percentile}`]?.[String(year)];
  const ib = inBase(year, rule.base);
  if (!row) return { state: "nodata", longest: null, missing: 0, filled: 0, inBase: ib, why: "no data" };
  const base = { missing: row.missing, filled: row.filled, inBase: ib };
  if (d.coverage[v.source][rule.base] < MIN_BASE_COVERAGE)
    return { ...base, state: "nodata", longest: null, why: `base period only ${d.coverage[v.source][rule.base] / 10}% complete` };
  if (row.missing > rule.maxMissing)
    return { ...base, state: "nodata", longest: null, why: `${row.missing} season days missing (limit ${rule.maxMissing})` };
  if (row.filled > rule.maxFilled)
    return { ...base, state: "nodata", longest: null, why: `${row.filled} days filled (limit ${rule.maxFilled})` };
  if (row.reps) {
    const share = row.reps.filter((r) => r >= rule.minSpell).length / row.reps.length;
    const mean = row.reps.reduce((a, b) => a + b, 0) / row.reps.length;
    const sorted = [...row.reps].sort((x, y) => x - y);
    return { ...base, state: share >= 0.5 ? "met" : "not", longest: mean, share, payoutSpell: sorted[Math.floor(sorted.length / 2)] };
  }
  return { ...base, state: (row.longest ?? 0) >= rule.minSpell ? "met" : "not", longest: row.longest ?? 0 };
}

export function dayIndex(d: SiteData, iso: string) {
  const start = Date.UTC(+d.series.start.slice(0, 4), +d.series.start.slice(5, 7) - 1, +d.series.start.slice(8, 10));
  const t = Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10));
  return Math.round((t - start) / 86400000);
}

export function doy(iso: string) {
  const y = +iso.slice(0, 4);
  return Math.round((Date.UTC(y, +iso.slice(5, 7) - 1, +iso.slice(8, 10)) - Date.UTC(y, 0, 1)) / 86400000) + 1;
}

export function seasonDates(year: number): string[] {
  const out: string[] = [];
  for (let t = Date.UTC(year, 5, 1); t <= Date.UTC(year, 8, 30); t += 86400000) out.push(new Date(t).toISOString().slice(0, 10));
  return out;
}

export function fmtDay(iso: string) {
  const m = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+iso.slice(5, 7) - 1];
  return `${+iso.slice(8, 10)} ${m}`;
}
