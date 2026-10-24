"use client";
import { decisionText, type ComparisonSeason } from "@/lib/comparison";
import { regionScan } from "@/lib/region";
import { MIN_BASE_COVERAGE, type Rule, type SiteData } from "@/lib/rule";
import { COUNTRY, IN_TURKIYE, SITES } from "@/lib/sites";

function cellClass(s: ComparisonSeason) {
  const p = s.policies.dual;
  return p.outcome === "dispute" ? (p.reason === "missing" ? "thin" : "contested") : p.outcome;
}

function cellTitle(s: ComparisonSeason) {
  const p = s.policies.dual;
  const why = p.reason === "missing" ? ` (${s.a.why ? "station " + s.a.why : "ERA5 " + (s.b.why ?? "has no verdict")})` : p.reason === "disagreement" ? " (station and ERA5 disagree)" : "";
  return `${s.year}: ${decisionText(p)}${why}`;
}

type Scan = ReturnType<typeof regionScan>;

function ScanTable({ scan, base, site, choose }: { scan: Scan; base: string; site: string; choose: (id: string) => void }) {
  const max = Math.max(1, ...scan.rows.filter((r) => !r.noNormal).map((r) => r.history.contested + r.history.thin));
  return (
    <div className="comparison-table-scroll" tabIndex={0} aria-label="Regional comparison table">
      <table className="region-table">
        <thead>
          <tr>
            <th scope="col">Place · station</th>
            <th scope="col">Your rule, 2021–2025</th>
            <th scope="col">Summers since 1966 the source decides</th>
            <th scope="col"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {scan.rows.map((r) => (
            <tr key={r.id} className={`${r.id === site ? "selected-summer" : ""}${r.noNormal ? " no-normal" : ""}`}>
              <th scope="row">
                {r.name}
                <span>
                  {r.station} · {Math.round(r.elevation)} m
                </span>
              </th>
              <td>
                <span className="region-strip" aria-label={r.recent.map(cellTitle).join("; ")}>
                  {r.recent.map((s) => (
                    <i key={s.year} className={cellClass(s)} title={cellTitle(s)}>
                      {String(s.year).slice(2)}
                    </i>
                  ))}
                </span>
              </td>
              <td>
                {r.noNormal ? (
                  <span className="region-count">
                    No station normal: only <strong>{r.baseCoverage / 10}%</strong> of {base} on record
                  </span>
                ) : (
                  <>
                    <span className="region-bar" aria-hidden>
                      <i className="contested" style={{ width: `${(r.history.contested / max) * 100}%` }} />
                      <i className="thin" style={{ width: `${(r.history.thin / max) * 100}%` }} />
                    </span>
                    <span className="region-count">
                      <strong>{r.history.contested}</strong> disagree{r.history.thin ? <> · <strong>{r.history.thin}</strong> too little data</> : null}{" "}
                      <span className="note">of {r.history.total}</span>
                    </span>
                  </>
                )}
              </td>
              <td>
                <button className="link" onClick={() => choose(r.id)} aria-label={`Design the agreement for ${r.name}`}>
                  {r.id === site ? "Selected" : "Open →"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const pct = (n: number, d: number) => Math.round((n / Math.max(1, d)) * 100);

/** The same signed settings applied to every pinned station (see lib/region.ts). */
export function RegionScan({ data, rule, site, setSite }: { data: Record<string, SiteData>; rule: Rule; site: string; setSite: (s: string) => void }) {
  const missing = SITES.filter((s) => !data[s.id]).length;
  if (missing) return <div className="card region-scan note">Loading the other {missing} stations…</div>;
  const home = regionScan(IN_TURKIYE, data, rule);
  const abroadSites = SITES.filter((s) => s.country !== "TR");
  const abroad = regionScan(abroadSites, data, rule);
  const countries = [...new Set(abroadSites.map((s) => COUNTRY[s.country]))];
  const base = rule.base.replace("-", "–");
  const choose = (id: string) => {
    setSite(id);
    document.getElementById("design")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  };

  return (
    <section className="card region-scan" aria-label={`Same rule at ${SITES.length} stations`}>
      <div className="eyebrow">Same rule, {home.rows.length} places · southern and western Türkiye</div>
      <h3>
        The record decides the payment in {home.placesWithConflict} of {home.rows.length} places
        {home.noNormal.length ? `. In ${home.noNormal.length} more, the public station record is too incomplete to define a normal at all.` : "."}
      </h3>
      <p className="note">
        Where both records can define a {base} normal, station and ERA5 supported different payment shares in <strong>{home.contested}</strong> of {home.decidable} summers
        1966–2025 ({pct(home.contested, home.decidable)}%). In 2021–2025, {home.recentOpen} of {home.usable} of those places would have
        needed the dispute fallback at least once.
        {home.noNormal.length > 0 && <> In {home.noNormal.join(", ")}, GHCN-Daily holds less than {MIN_BASE_COVERAGE / 10}% of the base period, so under this rule the
        station provider abstains every summer and a station-only scheme could not run.</>}
        {" "}Change the rule above and every row is recomputed; click a place to design its agreement.
      </p>
      <ScanTable scan={home} base={base} site={site} choose={choose} />

      <div className="eyebrow region-abroad">The same engine, unchanged · {abroad.rows.length} places in {countries.join(", ")}</div>
      <h3>
        Outside Türkiye the record decides the payment in {abroad.placesWithConflict} of {abroad.usable} places
        {abroad.noNormal.length ? `; in ${abroad.noNormal.length} more the station cannot define a normal.` : "."}
      </h3>
      <p className="note">
        Nothing here was tuned or written for these places: the same code and the same settings, with each place's own GHCN-Daily station and ERA5 grid cell. Station
        and ERA5 supported different payment shares in <strong>{abroad.contested}</strong> of {abroad.decidable} summers ({pct(abroad.contested, abroad.decidable)}%).
        Each can be signed and settled in step 3 like the Turkish stations. Summer clocks there are UTC+3 as in Türkiye, so the season days line up; other time zones
        need the window shifted, not new code.
      </p>
      <ScanTable scan={abroad} base={base} site={site} choose={choose} />

      <p className="region-legend note">
        <span><i className="pay" /> pays</span>
        <span><i className="refund" /> refunds</span>
        <span><i className="contested" /> records disagree → dispute</span>
        <span><i className="thin" /> too little data → dispute</span>
      </p>
      <p className="note">
        Each place's “unusually hot” line comes from its own station and ERA5 grid cell; only the settings are shared. Station records are not homogenised. This is an
        exploratory scan over summers we have already seen, not a validation. It shows where a second record changes the decision, not which record is right.
      </p>
    </section>
  );
}
