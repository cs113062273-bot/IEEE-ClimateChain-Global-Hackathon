"use client";
import { COMPARISON_YEARS, decisionText, type ComparisonSeason } from "@/lib/comparison";
import { LAST10, NOW, ON_TARGET, TARGETS, THEN, differences, disputes, findRules, heldDeposits, meanPayment, sameRule, swing, type Candidate } from "@/lib/finder";
import { ladderOf, ladderText } from "@/lib/rule";
import type { Rule, SiteData, Verdict } from "@/lib/rule";

export const definition = (r: Rule) =>
  `Above the ${r.percentile}th percentile of ${r.base.replace("-", "–")}, ${r.minSpell}+ days in a row${r.payout === "graded" ? " (graded)" : ""}`;
const span = ([a, b]: [number, number]) => `${a}–${String(b).slice(2)}`;
const cellClass = (s: ComparisonSeason) => {
  const p = s.policies.dual;
  return p.outcome === "dispute" ? (p.reason === "missing" ? "thin" : "contested") : p.outcome;
};
const spell = (v: Verdict) => (v.state === "nodata" ? "no verdict" : `${v.longest} d`);
export const onTarget = (c: Candidate, target: number) => c.returnPeriod !== null && Math.abs(Math.log(c.returnPeriod / target)) <= ON_TARGET;
export const every = (rp: number | null) => (rp === null ? "never" : `1 in ${rp.toFixed(1)}`);

export function DesignStep({ n, title, children }: { n: number; title: string; children?: React.ReactNode }) {
  return (
    <div className="design-step">
      <span className="sub-num" aria-label={`Part ${n} of 4`}>{n}/4</span>
      <h3>{title}</h3>
      {children && <p className="note">{children}</p>}
    </div>
  );
}

/**
 * Steps 1–2 of the design: say how often the relief should pay and what happens
 * when the records disagree, then compare complete rules that meet it.
 */
export function RuleFinder({ d, rule, setRule, target, setTarget }: {
  d: SiteData; rule: Rule; setRule: (r: Rule) => void; target: number; setTarget: (t: number) => void;
}) {
  const { current, picks, excluded } = findRules(d, rule, target);
  const cols: { label: string; c: Candidate; isCurrent: boolean }[] = [
    { label: "Your rule now", c: current, isCurrent: true },
    ...picks.map((c, i) => ({ label: `Option ${"ABC"[i]}`, c, isCurrent: sameRule(c.rule, rule) })),
  ];
  const diffs = differences(cols.map((x) => x.c));
  const pay = rule.onDispute === "pay";
  const graded = rule.payout === "graded";
  const pctOf = (x: number) => `${Math.round(x * 100)}%`;

  return (
    <>
      <section className="design-part" aria-label="Purpose">
        <DesignStep n={1} title="Purpose: how often should the community be paid?">
          Anticipatory-action triggers are set this way, e.g. a 1-in-5-year level in IFRC's Mali flood protocol.
        </DesignStep>
        <div className="purpose-controls">
          <div className="field">
            About one summer in
            <div className="seg" role="group" aria-label="Target payout frequency">
              {TARGETS.map((t) => (
                <button key={t} aria-pressed={target === t} onClick={() => setTarget(t)}>
                  1 in {t}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            How much is paid
            <div className="seg" role="group" aria-label="Payout size">
              <button aria-pressed={!graded} onClick={() => setRule({ ...rule, payout: "flat" })}>all or nothing</button>
              <button aria-pressed={graded} onClick={() => setRule({ ...rule, payout: "graded" })}>grows with the heatwave</button>
            </div>
          </div>
          <div className="field">
            If the records disagree and the three parties can't agree, the money
            <div className="seg" role="group" aria-label="Dispute fallback">
              <button aria-pressed={!pay} onClick={() => setRule({ ...rule, onDispute: "refund" })}>returns to the fund</button>
              <button aria-pressed={pay} onClick={() => setRule({ ...rule, onDispute: "pay" })}>goes to the cooperative</button>
            </div>
          </div>
        </div>
        <p className="note">
          {graded
            ? `Graded: ${ladderText(ladderOf(rule))} of the deposit. The share both records support is paid as soon as the published data show the spell, during the season; only the difference between them can be disputed.`
            : "All or nothing: the full deposit at the threshold, so any disagreement between the records puts all of it in dispute."}{" "}
          The target counts every summer the community receives something{pay ? ", including disputes, because the fallback pays out" : ""}.
        </p>
      </section>

      <section className="design-part finder" aria-label="Choose a rule by its purpose">
        <DesignStep n={2} title={`Compare complete rules for ${d.site.name}`}>
          Each option keeps your gap rule, data limits, fallback and deposit; only the definition of “unusually hot” changes. Summers {span(NOW)}.
        </DesignStep>
        <div className="comparison-table-scroll" tabIndex={0} aria-label="Rule options">
          <table className="finder-table">
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Measure</span></th>
                {cols.map(({ label, c, isCurrent }) => (
                  <th scope="col" key={label} className={isCurrent ? "chosen-policy" : ""}>
                    {label}
                    <span>{definition(c.rule)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="finder-main">
                <th scope="row">Community paid<span>every payment, as signed</span></th>
                {cols.map(({ label, c }) => (
                  <td key={label}>
                    <strong className={onTarget(c, target) ? "on-target" : ""}>{every(c.returnPeriod)}</strong>
                    <span>
                      {c.now.finalPays} of {c.now.summers}: {c.now.pays} by agreement{c.now.finalPays > c.now.pays ? ` + ${c.now.finalPays - c.now.pays} by fallback` : ""}
                      {onTarget(c, target) ? " · on target" : ""}
                    </span>
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Average payment<span>share of the deposit, when paid</span></th>
                {cols.map(({ label, c }) => <td key={label}><strong>{pctOf(meanPayment(c.now))}</strong></td>)}
              </tr>
              <tr className="finder-hinge">
                <th scope="row">Payments that hinge on one day<span>if the rule needed one day more · one day fewer</span></th>
                {cols.map(({ label, c }) => (
                  <td key={label}>
                    <strong className={swing(c.hinge) <= 1 ? "steady" : ""}>{swing(c.hinge)}</strong>
                    <span>{c.hinge.noDayToSpare} paid with no day to spare · {c.hinge.oneDayShort} missed by one day</span>
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Decided by the data alone<span>share of 30 deposits, no dispute needed</span></th>
                {cols.map(({ label, c }) => (
                  <td key={label}>
                    <strong>{pctOf(1 - heldDeposits(c.now) / c.now.summers)}</strong>
                    <span>{heldDeposits(c.now).toFixed(1)} deposits held in dispute over {disputes(c.now)} summers ({c.now.contested} records disagree · {c.now.thin} data gaps)</span>
                  </td>
                ))}
              </tr>
              <tr>
                <th scope="row">Last 10 summers<span>community paid, {span(LAST10)}</span></th>
                {cols.map(({ label, c }) => <td key={label}><strong>{c.last10.finalPays} of {c.last10.summers}</strong></td>)}
              </tr>
              <tr>
                <th scope="row">Heat that met this definition<span>ERA5 alone, {span(THEN)} → {span(NOW)}</span></th>
                {cols.map(({ label, c }) => <td key={label}><strong>{c.then.era5Heat} → {c.now.era5Heat}</strong><span>of 30 summers</span></td>)}
              </tr>
              <tr>
                <th scope="row">{COMPARISON_YEARS[0]}–{COMPARISON_YEARS.at(-1)}<span>pay · refund · dispute</span></th>
                {cols.map(({ label, c }) => (
                  <td key={label}>
                    <span className="region-strip" aria-label={c.recent.map((s) => `${s.year}: ${decisionText(s.policies.dual)}`).join("; ")}>
                      {c.recent.map((s) => <i key={s.year} className={cellClass(s)} title={`${s.year}: ${decisionText(s.policies.dual)}`}>{String(s.year).slice(2)}</i>)}
                    </span>
                  </td>
                ))}
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <th scope="row"><span className="sr-only">Choose</span></th>
                {cols.map(({ label, c, isCurrent }) => (
                  <td key={label}>
                    {isCurrent ? (
                      <span className="chip good">{label === "Your rule now" ? "Adopted" : "= your rule"}</span>
                    ) : (
                      <button className="btn" onClick={() => setRule(c.rule)} aria-label={`Use ${label}: ${definition(c.rule)}`}>Adopt this rule</button>
                    )}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
        <p className="note finder-rank">
          Thirty summers hold only a handful of payments, so the count is noisy: options within about 25% of the target count as equally close. Among
          them, less money held in dispute comes first, then fewer payments that hinge on a single day.
        </p>
        <p className="finder-climate">
          Under your rule, ERA5 met the definition in <strong>{current.then.era5Heat}</strong> of 30 summers {span(THEN)} and <strong>{current.now.era5Heat}</strong> in{" "}
          {span(NOW)}. A frequency calibrated on past summers drifts as the climate warms, so the target and this calibration are signed with the rule.
        </p>
        {(diffs.length > 0 || excluded.length > 0) && (
          <details className="finder-why">
            <summary>Why the options decide differently{excluded.length ? ", and which definitions cannot work here" : ""}</summary>
            {diffs.length > 0 && (
              <ul>
                {diffs.map((dif) => (
                  <li key={dif.year}>
                    <b>{dif.year}</b>
                    {dif.rows.map(({ rule: r, season: s }, i) => (
                      <span key={i}>
                        {cols[i].label}: station {spell(s.a)}, ERA5 {spell(s.b)}, needs {r.minSpell} → <em className={s.policies.dual.outcome}>{decisionText(s.policies.dual)}</em>
                      </span>
                    ))}
                  </li>
                ))}
              </ul>
            )}
            {excluded.length > 0 && (
              <p className="note">
                Not offered: {excluded.map((x) => `${x.percentile}th percentile of ${x.base.replace("-", "–")} (${x.why})`).join("; ")}.
              </p>
            )}
          </details>
        )}
      </section>
    </>
  );
}
