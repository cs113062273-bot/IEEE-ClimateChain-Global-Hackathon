import { agreementOutcome, ladderOf, settle, type Outcome, type Rule, type SiteData, type Verdict } from "./rule";

// Counterfactual policies, not new deployable contract modes. Every policy uses
// the same threshold, data limits, deposit and unresolved-dispute fallback.
export const COMPARISON_YEARS = [2021, 2022, 2023, 2024, 2025];
export const DEMO_AMOUNT_CENTS = 5_000_000;
export const COMPARISON_ASSUMPTIONS = {
  reportDays: 14,
  disputeDays: 30,
  reporting: "Both providers report promptly after the season; \"not enough data\" is a report too, so a dispute opens at once. Only a silent provider would make settlement wait for the 14-day report deadline (not modelled).",
  resolution: "No unanimous dispute resolution; apply the signed fallback as soon as eligible. Transactions still need an operator.",
  timing: "Modelled whole days after season end, not measured delivery time. Excludes data publication lag and transaction latency.",
  evaluation: "Retrospective comparison on pinned final data, not an independent holdout or a reconstruction of what was available at the time.",
};

export type Policy = "station" | "era5" | "dual";
export interface PolicyResult {
  outcome: Outcome;
  reason: "agreement" | "disagreement" | "missing";
  final: "pay" | "refund"; // does the community receive anything once the dispute (if any) is resolved
  payoutCents: number; // what the community receives in the end
  paidNowCents: number; // released by the data alone right after the season
  refundedNowCents: number;
  contestedCents: number; // held for the unanimous vote or the fallback
  // Earliest fallback-only execution under the assumptions above, rounded to
  // whole days. An abstention is a report, so it does not wait for a deadline.
  modelledDays: number;
}
export interface ComparisonSeason {
  year: number;
  a: Verdict;
  b: Verdict;
  policies: Record<Policy, PolicyResult>;
}

function result(split: { payNow: number; refundNow: number; contested: number }, missing: boolean, rule: Rule, amountCents: number): PolicyResult {
  const cents = (x: number) => Math.round(x * amountCents);
  const outcome: Outcome = split.contested > 1e-9 ? "dispute" : split.payNow > 0 ? "pay" : "refund";
  const contestedCents = outcome === "dispute" ? cents(split.contested) : 0;
  const paidNowCents = cents(split.payNow);
  const payoutCents = paidNowCents + (rule.onDispute === "pay" ? contestedCents : 0);
  return {
    outcome,
    reason: outcome !== "dispute" ? "agreement" : missing ? "missing" : "disagreement",
    final: payoutCents > 0 ? "pay" : "refund",
    payoutCents, paidNowCents, refundedNowCents: amountCents - paidNowCents - contestedCents, contestedCents,
    modelledDays: outcome !== "dispute" ? 0 : COMPARISON_ASSUMPTIONS.disputeDays,
  };
}

export function compareSeason(d: SiteData, rule: Rule, year: number, amountCents = DEMO_AMOUNT_CENTS): ComparisonSeason {
  const ag = agreementOutcome(d, rule, year);
  const single = (v: Verdict) => result(settle([v], ladderOf(rule)), v.state === "nodata", rule, amountCents);
  return { year, a: ag.a, b: ag.b, policies: {
    station: single(ag.a), era5: single(ag.b),
    dual: result(ag, ag.a.state === "nodata" || ag.b.state === "nodata", rule, amountCents),
  } };
}

export function compareHistory(d: SiteData, rule: Rule, years = COMPARISON_YEARS, amountCents = DEMO_AMOUNT_CENTS) {
  const seasons = years.map((y) => compareSeason(d, rule, y, amountCents));
  const summaries = Object.fromEntries((["station", "era5", "dual"] as Policy[]).map((policy) => {
    const rows = seasons.map((s) => s.policies[policy]);
    return [policy, {
      directPays: rows.filter((r) => r.outcome === "pay").length,
      directRefunds: rows.filter((r) => r.outcome === "refund").length,
      disputes: rows.filter((r) => r.outcome === "dispute").length,
      payoutCents: rows.reduce((n, r) => n + r.payoutCents, 0),
      paidNowCents: rows.reduce((n, r) => n + r.paidNowCents, 0),
      contestedCents: rows.reduce((n, r) => n + r.contestedCents, 0),
      modelledDaysTotal: rows.reduce((n, r) => n + r.modelledDays, 0),
    }];
  })) as Record<Policy, { directPays: number; directRefunds: number; disputes: number; payoutCents: number; paidNowCents: number; contestedCents: number; modelledDaysTotal: number }>;
  return { seasons, summaries };
}

export function verdictLabel(v: Verdict) {
  return v.state === "nodata" ? "No verdict" : `${v.longest?.toFixed(v.inBase ? 1 : 0)} hot days in a row`;
}

/** "Pay", "Pay 40%", "Refund", "Dispute → refund" or, for a partial dispute, "Pay 40%, return 30% now · dispute 30% → refund". */
export function decisionText(r: PolicyResult) {
  const total = r.paidNowCents + r.refundedNowCents + r.contestedCents;
  const pct = (c: number) => `${Math.round((c / total) * 100)}%`;
  if (r.outcome === "pay") return r.paidNowCents < total ? `Pay ${pct(r.paidNowCents)}` : "Pay";
  if (r.outcome === "refund") return "Refund";
  const to = r.payoutCents > r.paidNowCents ? "pay" : "refund";
  if (r.contestedCents === total) return `Dispute → ${to}`;
  const now = [r.paidNowCents ? `Pay ${pct(r.paidNowCents)}` : "", r.refundedNowCents ? `${r.paidNowCents ? "return" : "Return"} ${pct(r.refundedNowCents)}` : ""]
    .filter(Boolean).join(", ");
  return `${now} now · dispute ${pct(r.contestedCents)} → ${to}`;
}

export function ruleFromSpec(spec: any): Rule {
  const fill = spec.sources.find((s: any) => s.id === "station")?.fill?.method ?? "none";
  const variant = { none: "station", era5_quantile_map: "station_qm", era5_monthly_linear: "station_linear", era5_raw: "station_raw" }[fill as string];
  if (!variant) throw new Error(`Unsupported station fill: ${fill}`);
  return {
    variant: variant as Rule["variant"], base: `${spec.rule.base_period[0].slice(0, 4)}-${spec.rule.base_period[1].slice(0, 4)}` as Rule["base"],
    percentile: spec.rule.percentile, minSpell: spec.rule.min_spell_days,
    maxMissing: spec.rule.max_missing_days, maxFilled: spec.rule.max_filled_days, onDispute: spec.settlement.on_dispute,
    payout: (spec.settlement.payout_ladder?.length ?? 1) > 1 ? "graded" : "flat",
    steps: (spec.settlement.payout_ladder?.length ?? 1) > 1
      ? spec.settlement.payout_ladder.map(([d, b]: [number, number]) => [d - spec.rule.min_spell_days, b] as [number, number])
      : undefined,
  };
}
