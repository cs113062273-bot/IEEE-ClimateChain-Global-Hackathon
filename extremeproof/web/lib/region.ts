import { COMPARISON_YEARS, compareSeason, type ComparisonSeason } from "./comparison";
import { MIN_BASE_COVERAGE, VARIANTS, agreementOutcome, type Rule, type SiteData } from "./rule";

/** Summers 1966–2025 in which the two records disagree, or one of them has no verdict, under this rule. */
export function historyCounts(d: SiteData, rule: Rule) {
  const past = d.years.filter((y) => y <= 2025);
  let contested = 0;
  let thin = 0;
  for (const y of past) {
    const { a, b, outcome } = agreementOutcome(d, rule, y);
    if (a.state === "nodata" || b.state === "nodata") thin++;
    else if (outcome === "dispute") contested++;
  }
  return { total: past.length, first: past[0], contested, thin };
}

export interface RegionRow {
  id: string;
  name: string;
  station: string;
  elevation: number;
  baseCoverage: number; // per mille of the base period on record at the station
  noNormal: boolean; // the station cannot define a normal under this rule, so provider A always abstains
  history: ReturnType<typeof historyCounts>;
  recent: ComparisonSeason[];
}

/** The same rule settings at every station; each keeps its own 30-year normal. */
export function regionScan(sites: { id: string; name: string }[], data: Record<string, SiteData>, rule: Rule) {
  const source = VARIANTS.find((v) => v.id === rule.variant)!.source;
  const rows: RegionRow[] = sites
    .map((s) => {
      const d = data[s.id];
      const baseCoverage = d.coverage[source][rule.base];
      return {
        id: s.id, name: s.name, station: d.station.id, elevation: d.station.elev_m, baseCoverage,
        noNormal: baseCoverage < MIN_BASE_COVERAGE,
        history: historyCounts(d, rule),
        recent: COMPARISON_YEARS.map((y) => compareSeason(d, rule, y)),
      };
    })
    .sort((x, y) => +x.noNormal - +y.noNormal || y.history.contested - x.history.contested || y.history.thin - x.history.thin);
  const usable = rows.filter((r) => !r.noNormal);
  return {
    rows,
    usable: usable.length,
    noNormal: rows.filter((r) => r.noNormal).map((r) => r.name),
    decidable: usable.reduce((n, r) => n + r.history.total - r.history.thin, 0),
    contested: usable.reduce((n, r) => n + r.history.contested, 0),
    placesWithConflict: usable.filter((r) => r.history.contested > 0).length,
    recentOpen: usable.filter((r) => r.recent.some((s) => s.policies.dual.outcome === "dispute")).length,
  };
}
