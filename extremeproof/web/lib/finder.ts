import { COMPARISON_YEARS, DEMO_AMOUNT_CENTS, compareSeason, type ComparisonSeason } from "./comparison";
import { verdict, type Base, type Rule, type SiteData } from "./rule";

// Choose a complete rule by its purpose. Anticipatory-action and index schemes
// state how often a trigger should fire as a return period ("1 in 5 years").
// Here every candidate keeps the same gap rule, data limits, fallback and
// deposit; only the definition of "unusually hot" and the spell length change.
//
// The target is the FINAL payment frequency: what the community receives when no
// unanimous resolution happens, i.e. payments by agreement plus disputes settled by
// a "pay" fallback. Payments by agreement alone are reported next to it.
//
// Thirty summers hold only a handful of payments, so a frequency fitted to them is
// noisy: one day more or less in the spell rule can move several payments. Options
// within ON_TARGET of the target are treated as equally close; among them fewer
// disputes rank first, then fewer payments that hinge on a single day.

export const TARGETS = [3, 5, 10] as const;
export const NOW: [number, number] = [1996, 2025];
export const THEN: [number, number] = [1966, 1995];
export const LAST10: [number, number] = [2016, 2025];
const BASES: Base[] = ["1961-1990", "1991-2020"];
const PERCENTILES = [90, 95] as const;
const SPELLS = [3, 4, 5, 6, 7, 8, 9, 10];
/** Within 25 % of the target return period counts as on target (1 in 4-6.25 for a 1-in-5 target). */
export const ON_TARGET = Math.log(1.25);

export interface WindowStats {
  summers: number;
  pays: number; // the data alone released a payment right after the season
  finalPays: number; // the community received something once disputes were resolved by the signed fallback
  refunds: number;
  contested: number; // the records disagree
  thin: number; // a provider has too little data
  waitingDays: number; // modelled days the deposit waits, summed over disputed summers
  era5Heat: number; // summers ERA5 alone says the rule was met: the climate signal, independent of station gaps
  payoutCents: number; // everything the community received
  paidNowCents: number; // of which released by the data alone
  contestedCents: number; // held for a dispute (the providers' difference)
}

/** Summers 1996-2025 whose final payment would change if the spell rule were one day longer or shorter. */
export interface Hinge {
  noDayToSpare: number; // paid, but would not with one more day required
  oneDayShort: number; // not paid, but would be with one day fewer required
}

export interface Candidate {
  rule: Rule;
  now: WindowStats;
  hinge: Hinge;
  then: WindowStats;
  last10: WindowStats;
  recent: ComparisonSeason[];
  returnPeriod: number | null; // summers per final payment, 1996-2025; null if it never paid
  agreementReturnPeriod: number | null; // summers per payment by agreement alone
  miss: number; // distance from the target on a log scale (0 = on target)
}

export function windowStats(d: SiteData, rule: Rule, [from, to]: [number, number]): WindowStats {
  const s: WindowStats = { summers: 0, pays: 0, finalPays: 0, refunds: 0, contested: 0, thin: 0, waitingDays: 0, era5Heat: 0,
    payoutCents: 0, paidNowCents: 0, contestedCents: 0 };
  for (let y = from; y <= to; y++) {
    const c = compareSeason(d, rule, y);
    const p = c.policies.dual;
    s.summers++;
    if (p.paidNowCents > 0) s.pays++;
    if (p.outcome === "refund") s.refunds++;
    else if (p.outcome === "dispute" && p.reason === "missing") s.thin++;
    else if (p.outcome === "dispute") s.contested++;
    if (p.final === "pay") s.finalPays++;
    s.payoutCents += p.payoutCents;
    s.paidNowCents += p.paidNowCents;
    s.contestedCents += p.contestedCents;
    s.waitingDays += p.modelledDays;
    if (verdict(d, { ...rule, variant: "era5" }, y).state === "met") s.era5Heat++;
  }
  return s;
}

export function hinge(d: SiteData, rule: Rule): Hinge {
  const pays = (minSpell: number, y: number) => compareSeason(d, { ...rule, minSpell }, y).policies.dual.final === "pay";
  const h: Hinge = { noDayToSpare: 0, oneDayShort: 0 };
  for (let y = NOW[0]; y <= NOW[1]; y++) {
    if (pays(rule.minSpell, y)) h.noDayToSpare += pays(rule.minSpell + 1, y) ? 0 : 1;
    else if (rule.minSpell > 1) h.oneDayShort += pays(rule.minSpell - 1, y) ? 1 : 0;
  }
  return h;
}

export const swing = (h: Hinge) => h.noDayToSpare + h.oneDayShort;

export function evaluate(d: SiteData, rule: Rule, target: number): Candidate {
  const now = windowStats(d, rule, NOW);
  const returnPeriod = now.finalPays ? now.summers / now.finalPays : null;
  return {
    rule, now, hinge: hinge(d, rule), then: windowStats(d, rule, THEN), last10: windowStats(d, rule, LAST10),
    recent: COMPARISON_YEARS.map((y) => compareSeason(d, rule, y)),
    returnPeriod,
    agreementReturnPeriod: now.pays ? now.summers / now.pays : null,
    miss: returnPeriod === null ? Infinity : Math.abs(Math.log(returnPeriod / target)),
  };
}

export const sameRule = (a: Rule, b: Rule) => (Object.keys(a) as (keyof Rule)[]).every((k) => a[k] === b[k]);

/**
 * The best spell length for each definition of "unusually hot" (base period ×
 * percentile), ranked by closeness to the target (all on-target options tie), then
 * fewer disputes, then fewer payments hinging on one day, then less waiting.
 * Returns the three best definitions next to the current rule.
 */
export function findRules(d: SiteData, current: Rule, target: number) {
  const best: Candidate[] = [];
  const excluded: { base: Base; percentile: number; why: string }[] = [];
  for (const base of BASES)
    for (const percentile of PERCENTILES) {
      const options = SPELLS.map((minSpell) => evaluate(d, { ...current, base, percentile, minSpell }, target));
      options.sort(rank);
      // A definition that never settles by agreement (e.g. the station cannot define this normal) is not a candidate,
      // even if a "pay" fallback would make it pay: then the data never decide anything.
      if (options.every((o) => o.now.pays === 0)) {
        const v = verdict(d, { ...current, base, percentile, minSpell: 6 }, NOW[1]);
        excluded.push({ base, percentile, why: v.why ?? "the two providers never agree that the rule was met" });
      } else best.push(options[0]);
    }
  best.sort(rank);
  return { current: evaluate(d, current, target), picks: best.slice(0, 3), excluded };
}

const closeness = (c: Candidate) => (c.miss <= ON_TARGET ? 0 : c.miss);

function rank(a: Candidate, b: Candidate) {
  // Money held in dispute, not the number of disputed summers: a graded rule disputes more often, over less.
  return closeness(a) - closeness(b) || a.now.contestedCents - b.now.contestedCents || swing(a.hinge) - swing(b.hinge) ||
    a.now.waitingDays - b.now.waitingDays || a.miss - b.miss || a.rule.minSpell - b.rule.minSpell;
}

export const disputes = (s: WindowStats) => s.contested + s.thin;
/** Deposits' worth held in dispute over the window, e.g. 2.4 = two and a half deposits. */
export const heldDeposits = (s: WindowStats) => s.contestedCents / DEMO_AMOUNT_CENTS;
/** Average payment when the community is paid, as a share of the deposit. */
export const meanPayment = (s: WindowStats) => (s.finalPays ? s.payoutCents / s.finalPays / DEMO_AMOUNT_CENTS : 0);

/** For each recent summer where the candidates decide differently, what each one saw. */
export function differences(cands: Candidate[]) {
  return COMPARISON_YEARS.flatMap((y, i) => {
    const outcomes = cands.map((c) => c.recent[i].policies.dual.outcome);
    if (outcomes.every((o) => o === outcomes[0])) return [];
    return [{ year: y, rows: cands.map((c) => ({ rule: c.rule, season: c.recent[i] })) }];
  });
}

/** One line for a signed purpose block, for summaries. */
export function purposeText(p: any) {
  if (!p) return null;
  const rp = p.final_pays ? ` (1 in ${(p.summers / p.final_pays).toFixed(1)})` : "";
  const byFallback = p.final_pays - p.agreement_pays;
  const [a, b] = Object.keys(p.era5_heat_summers ?? {});
  const h = p.one_day_hinge;
  return `Pay about 1 summer in ${p.target_return_period_summers}, counting payments by the signed fallback. When signed, this rule had paid in ${p.final_pays} of ${p.summers} summers ${p.calibration_window.join("–")}${rp}: ${p.agreement_pays} by agreement${byFallback ? `, ${byFallback} by the fallback after a dispute` : ""}; ${p.disputes_records_disagree + p.disputes_too_little_data} disputes in all${h ? `; ${h.no_day_to_spare} payments had no day to spare and ${h.one_day_short} summers missed by one day` : ""}${a ? `. ERA5 met its definition in ${p.era5_heat_summers[a]} of the summers ${a.replace("-", "–")} and ${p.era5_heat_summers[b]} of ${b.replace("-", "–")}` : ""}.`;
}

/**
 * The purpose block signed with the rule: integers and strings only, so it fits
 * the canonical text. It records intent and the calibration the parties saw.
 */
export function purposeBlock(d: SiteData, rule: Rule, target: number, inputSha256: string) {
  const c = evaluate(d, rule, target);
  return {
    target_return_period_summers: target,
    calibration_window: [`${NOW[0]}`, `${NOW[1]}`],
    summers: c.now.summers,
    final_pays: c.now.finalPays,
    on_dispute: rule.onDispute,
    payout: rule.payout ?? "flat",
    mean_payment_permille: Math.round(meanPayment(c.now) * 1000),
    agreement_pays: c.now.pays,
    disputes_records_disagree: c.now.contested,
    disputes_too_little_data: c.now.thin,
    one_day_hinge: { no_day_to_spare: c.hinge.noDayToSpare, one_day_short: c.hinge.oneDayShort },
    era5_heat_summers: { [`${THEN[0]}-${THEN[1]}`]: c.then.era5Heat, [`${NOW[0]}-${NOW[1]}`]: c.now.era5Heat },
    computed_from: { file: `web/public/data/${d.site.id}.json`, sha256: inputSha256 },
  };
}
