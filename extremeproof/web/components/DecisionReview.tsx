"use client";
import { useState } from "react";
import { COMPARISON_ASSUMPTIONS, COMPARISON_YEARS, DEMO_AMOUNT_CENTS, compareHistory, compareSeason, decisionText, ruleFromSpec, verdictLabel, type ComparisonSeason, type Policy, type PolicyResult } from "@/lib/comparison";
import type { Rule, SiteData, Verdict } from "@/lib/rule";
import { asset } from "@/lib/edition";
import { historyCounts } from "@/lib/region";

// The signed two-source rule comes first: on a phone it is the column you see without scrolling.
const POLICIES: { id: Policy; label: string; sub: string }[] = [
  { id: "dual", label: "Your two-source rule", sub: "A + B must agree · the rule you sign" },
  { id: "station", label: "Station only", sub: "A alone, same gap rule" },
  { id: "era5", label: "ERA5 only", sub: "B alone" },
];
const units = (cents: number) => (cents / 100).toLocaleString("en-US");
const days = (v: Verdict) => (v.longest === null ? "no verdict" : `${v.inBase ? v.longest.toFixed(1) : v.longest} hot days in a row`);
const final = (r: PolicyResult) => (r.final === "pay" ? "pay" : "refund");

function inspectSummer(year: number, setYear: (year: number) => void) {
  setYear(year);
  const el = document.getElementById("summer-decision") as HTMLDetailsElement | null;
  if (el) el.open = true;
  el?.scrollIntoView({
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
    block: "start",
  });
}

function Outcome({ r }: { r: PolicyResult }) {
  return <span className={`decision-outcome ${r.outcome}`}><strong>{decisionText(r)}</strong><span>{r.modelledDays ? `Modelled ~${r.modelledDays} days · ${units(r.payoutCents)} to community` : `Modelled: season end · ${units(r.payoutCents)} to community`}</span></span>;
}

/** Table cell: the outcome and the money, nothing repeated. */
function Cell({ r }: { r: PolicyResult }) {
  return <span className={`decision-outcome ${r.outcome}`}><strong>{decisionText(r)}</strong><span>{units(r.payoutCents)} DEMO{r.modelledDays ? ` · ~${r.modelledDays} days` : ""}</span></span>;
}

export function SignedDecisionReview({ spec, data }: { spec: any; data: Record<string, SiteData> }) {
  const row = compareSeason(data[spec.site.id], ruleFromSpec(spec), spec.observation_year, spec.settlement.amount_cents);
  return <div className="signed-decision" aria-label="Consequences of the signed agreement">
    <strong>What this signed rule means</strong>
    <p>For {spec.site.name} {row.year}, ERA5 alone would {decisionText(row.policies.era5).toLowerCase()}; this agreement would {decisionText(row.policies.dual).toLowerCase()}.
      {row.policies.dual.outcome === "dispute" ? ` ${row.policies.dual.paidNowCents ? `${units(row.policies.dual.paidNowCents)} DEMO is paid as soon as the readings show the spell, at the latest when the season ends. ` : ""}Without a unanimous resolution, the fallback leaves the community with ${units(row.policies.dual.payoutCents)} DEMO in all after about ${row.policies.dual.modelledDays} days.` : ` It sends ${units(row.policies.dual.payoutCents)} DEMO to the community.`}</p>
  </div>;
}

function DecisionBrief({ d, rule, setRule, seasons, year, setYear, onReview }: {
  d: SiteData; rule: Rule; setRule: (r: Rule) => void; seasons: ComparisonSeason[]; year: number; setYear: (y: number) => void; onReview: () => void;
}) {
  const clear = seasons.filter((s) => s.policies.dual.outcome !== "dispute");
  const contested = seasons.filter((s) => s.policies.dual.reason === "disagreement");
  const thin = seasons.filter((s) => s.policies.dual.reason === "missing");
  const open = [...contested, ...thin].sort((x, y) => x.year - y.year);
  const paid = clear.filter((s) => s.policies.dual.final === "pay").map((s) => s.year);
  const refunded = clear.filter((s) => s.policies.dual.final === "refund").map((s) => s.year);
  const openPaid = open.reduce((n, s) => n + s.policies.dual.payoutCents, 0);
  const openWait = Math.max(0, ...open.map((s) => s.policies.dual.modelledDays));
  const openNow = open.reduce((n, s) => n + s.policies.dual.paidNowCents, 0);
  const openHeld = open.reduce((n, s) => n + s.policies.dual.contestedCents, 0);
  const h = historyCounts(d, rule);
  return <section className="brief" aria-label="Decision brief">
    <div className="eyebrow">Your decision · {d.site.name} · summers 2021–2025</div>
    <h3>{open.length === 0 ? "Every summer is settled by the data. Nothing to negotiate." : `${open.length} of ${seasons.length} summers need a decision from you now.`}</h3>
    <ol className="brief-list">
      <li><span className="brief-tag ok">Records agree</span><span>
        <strong>{clear.length} {clear.length === 1 ? "summer" : "summers"}</strong> settle themselves:
        {paid.length ? ` pay in ${paid.join(", ")}` : ""}{paid.length && refunded.length ? ";" : ""}{refunded.length ? ` refund in ${refunded.join(", ")}` : ""}{clear.length ? "." : " none."}
      </span></li>
      {contested.map((s) => <li key={s.year}><span className="brief-tag warn">Records disagree</span><span>
        <strong>{s.year}:</strong> station {days(s.a)}, ERA5 {days(s.b)}; the rule needs {rule.minSpell}. A station-only rule would {decisionText(s.policies.station).toLowerCase()}, an ERA5-only rule would {decisionText(s.policies.era5).toLowerCase()}.
        {s.policies.dual.paidNowCents ? ` Both support ${units(s.policies.dual.paidNowCents)} DEMO, paid at once; only ${units(s.policies.dual.contestedCents)} is in question.` : ""}{" "}
        <button className="link" onClick={() => inspectSummer(s.year, setYear)} aria-label={`Show summer ${s.year} below`}>Inspect {s.year}</button>
      </span></li>)}
      {thin.map((s) => <li key={s.year}><span className="brief-tag warn">Too little data</span><span>
        <strong>{s.year}:</strong> {s.a.why ? `station ${s.a.why}` : `ERA5 ${s.b.why ?? "has no verdict"}`}, so {s.a.why ? "the station provider" : "the ERA5 provider"} abstains and the summer cannot settle itself.{" "}
        <button className="link" onClick={() => inspectSummer(s.year, setYear)} aria-label={`Show summer ${s.year} below`}>Inspect {s.year}</button>
      </span></li>)}
      {open.length > 0 && <li className="brief-choice"><span className="brief-tag">Decide now</span><div>
        <span>If the three parties cannot agree after such a summer, the money should</span>
        <div className="seg" role="group" aria-label="Decision for unsettled summers">
          <button aria-pressed={rule.onDispute === "refund"} onClick={() => setRule({ ...rule, onDispute: "refund" })}>return to the fund</button>
          <button aria-pressed={rule.onDispute === "pay"} onClick={() => setRule({ ...rule, onDispute: "pay" })}>go to the cooperative</button>
        </div>
        <span className="brief-consequence">→ in {open.map((s) => s.year).join(", ")} the cooperative receives <strong>{units(openPaid)} DEMO</strong>{openNow ? (openPaid > openNow ? `: ${units(openNow)} by the end of the season, ${units(openPaid - openNow)} about ${openWait} days later (modelled)` : `, all of it by the end of the season; the ${units(openHeld)} DEMO in question returns to the fund after about ${openWait} days (modelled)`) : `, ${open.length > 1 && open.some((s) => s.policies.dual.modelledDays !== openWait) ? "up to" : "about"} ${openWait} days after the season (modelled)`}.</span>
      </div></li>}
    </ol>
    <p className="brief-context">
      Not a one-off: under this rule, the two records disagreed in <strong>{h.contested}</strong> and data were too thin in <strong>{h.thin}</strong> of the {h.total} summers {h.first}–2025.
    </p>
    <div className="brief-next">
      <button className="btn" onClick={onReview}>Next: review & sign this rule for {year} →</button>
      <span className="note">Opens a draft. Nothing is locked until all three parties sign.</span>
    </div>
  </section>;
}

function PaymentUse() {
  return <details className="comparison-method"><summary>What is the payment for?</summary><div className="stack">
    <p><strong>Example design, no partner yet:</strong> a heat-relief payment into a farmers' cooperative's hardship fund, which the cooperative distributes to
      members under its own rules: the share both records support can arrive during the summer (for shade, water, cooling and lost working days), the rest
      after the season, when heat damage to the harvest shows.</p>
    <p><strong>A different use: income protection during heat.</strong> SEWA's heat insurance for informal women workers in India addresses wages lost during extreme heat.
      Its design draws on members' experiences and health expertise, not just weather records
      (<a href="https://www.cgap.org/research/publication/confronting-climate-and-health-nexus-lessons-self-employed-womens-association" target="_blank" rel="noreferrer">CGAP case study</a>).
      ExtremeProof pays a fund, not individual wages, and only on observed heat.</p>
    <p><strong>Existing practice for seasonal heat indices:</strong> India's Restructured Weather Based Crop Insurance Scheme lists high temperature (heat) among the
      weather perils for crop-season cover (<a href="https://www.iffcotokio.co.in/content/dam/iffcotokio/policy-wordings/other-insurance/RWBCIS_Policy_Wording.pdf" target="_blank" rel="noreferrer">policy wording</a>).</p>
    <p>ExtremeProof is not insurance and has no fund, cooperative or verified need data.</p>
  </div></details>;
}

export function DecisionReview({ d, rule, setRule, year, setYear, onReview }: {
  d: SiteData; rule: Rule; setRule: (r: Rule) => void; year: number; setYear: (y: number) => void; onReview: () => void;
}) {
  const { seasons, summaries } = compareHistory(d, rule);
  const selected = compareSeason(d, rule, year);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setError(null);
    try {
      const response = await fetch(asset(`/data/${d.site.id}.json`));
      if (!response.ok) throw new Error("Could not read the comparison input. Reload the page and try again.");
      const bytes = await response.arrayBuffer();
      const pinned = JSON.parse(new TextDecoder().decode(bytes));
      if (JSON.stringify(pinned) !== JSON.stringify(d)) throw new Error("The data changed since this page loaded. Reload before exporting.");
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      const sha256 = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
      const report = {
        schema: "extremeproof.decision-comparison.v1", site: d.site, rule, amount_cents_per_season: DEMO_AMOUNT_CENTS,
        input: { file: `web/public/data/${d.site.id}.json`, sha256 }, years: COMPARISON_YEARS,
        assumptions: COMPARISON_ASSUMPTIONS, ...compareHistory(d, rule), selected: compareSeason(d, rule, year),
        scope: "Unsigned design comparison. Single-source policies are counterfactuals, not deployable modes. Use the verification bundle after signing to check an executed agreement.",
      };
      const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
      const a = document.createElement("a"); a.href = url; a.download = `extremeproof-${d.site.id}-decision-comparison.json`; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return <div className="decision-review" aria-label="Compare relief decisions">
    <DecisionBrief d={d} rule={rule} setRule={setRule} seasons={seasons} year={year} setYear={setYear} onReview={onReview} />
    <details className="comparison-detail"><summary>Summer by summer: your two-source rule next to station only and ERA5 only, 2021–2025</summary>
    <div className="decision-heading">
      <div><div className="eyebrow">Summer by summer</div><h3>Who gets paid under this rule?</h3><p>Same summers, heat threshold and {units(DEMO_AMOUNT_CENTS)} DEMO deposit per season. Only the source that decides changes. Click a summer to inspect it.</p></div>
      <button className="btn ghost" onClick={download}>Download comparison</button>
    </div>
    <div className="comparison-table-scroll" tabIndex={0} aria-label="Historical payout comparison">
      <table className="comparison-table">
        <caption>{d.site.name} · 2021–2025 · retrospective design comparison</caption>
        <thead><tr><th scope="col">Summer</th>{POLICIES.map((p) => <th scope="col" key={p.id} className={p.id === "dual" ? "chosen-policy" : ""}>{p.label}<span>{p.sub}</span></th>)}</tr></thead>
        <tbody>{seasons.map((s) => <tr key={s.year} className={s.year === year ? "selected-summer" : ""}>
          <th scope="row"><button onClick={() => inspectSummer(s.year, setYear)} aria-pressed={s.year === year} aria-label={`Inspect summer ${s.year}`}>{s.year}<span>{s.year === year ? "Selected" : "Inspect →"}</span></button></th>
          {POLICIES.map((p) => <td key={p.id} className={p.id === "dual" ? "chosen-policy" : ""}><Cell r={s.policies[p.id]} /></td>)}
        </tr>)}</tbody>
        <tfoot><tr><th scope="row">Five separate seasons<span>Totals if every dispute follows the fallback</span></th>{POLICIES.map((p) => <td key={p.id} className={p.id === "dual" ? "chosen-policy" : ""}><strong>{units(summaries[p.id].payoutCents)} DEMO</strong><span>{summaries[p.id].directPays} pay · {summaries[p.id].directRefunds} refund · {summaries[p.id].disputes} {summaries[p.id].disputes === 1 ? "dispute" : "disputes"}</span></td>)}</tr></tfoot>
      </table>
    </div>
    </details>
    <details className="comparison-detail" id="summer-decision"><summary>Inspect one summer: {d.site.name} {year}, {decisionText(selected.policies.dual).toLowerCase()}</summary>
    <div className="summer-review" aria-label="Selected summer decision">
      <div><span className="eyebrow">Inspect one summer</span><h3>{d.site.name} {year}</h3><p><strong>Station:</strong> {verdictLabel(selected.a)}. <strong>ERA5:</strong> {verdictLabel(selected.b)}. The rule needs {rule.minSpell} days.</p>
        {(selected.a.why || selected.b.why) && <p className="err">{selected.a.why ?? selected.b.why}</p>}
        <p className="note">Station days filled: {selected.a.filled}. Missing: {selected.a.missing}.</p></div>
      <div className="summer-consequence"><Outcome r={selected.policies.dual} /><p>{selected.policies.dual.outcome === "dispute" ? selected.policies.dual.reason === "missing" ? "A provider reports that its data are too thin for a verdict. That is a report, so the dispute window opens at once: unanimous resolution or the signed fallback decides." : (selected.policies.dual.contestedCents < selected.policies.dual.paidNowCents + selected.policies.dual.refundedNowCents + selected.policies.dual.contestedCents
          ? "Both sources report, but support different shares. The share both support is settled at once; only the difference goes to unanimous resolution or the signed fallback."
          : "Both sources can report, but give opposite answers. Only unanimous resolution or the signed fallback decides the payment.") : "Both providers give the same answer. No dispute window is needed."}</p>
        <button className="btn" onClick={onReview}>Review & sign this two-source rule →</button></div>
    </div>
    </details>
    <PaymentUse />
    <details className="comparison-method"><summary>How to read this comparison</summary><div className="stack">
      <p>Station only and ERA5 only are what-if columns: the same settings, decided by one source. The contract does not offer them.</p>
      <p><strong>Timing is modelled, not observed.</strong> The share both providers support is released during the season, once the spell is in the published data; an unresolved difference waits for the 30-day dispute window after the season. All three parties may resolve a dispute earlier. Data publication delays are excluded; an operator must still submit transactions. These are not guaranteed maximum waiting times.</p>
      <p><strong>These are five separate past seasons, not an annual budget or a forecast.</strong> 2021–2025 are the first summers after both base periods.</p>
      <p>The download records your settings and the input data's fingerprint, so anyone can recompute this table. It is not signed; to check an executed agreement, use the bundle in step 6.</p>
    </div></details>
    {error && <p className="err" role="alert">{error}</p>}
  </div>;
}
