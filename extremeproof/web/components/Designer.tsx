"use client";
import { Matrix, type CellState, type MatrixRow } from "./charts";
import { DecisionReview } from "./DecisionReview";
import { SitePicker } from "./SitePicker";
import { DesignStep, RuleFinder, definition, every, onTarget } from "./RuleFinder";
import { evaluate } from "@/lib/finder";
import { GRADED_STEPS, VARIANTS, agreementOutcome, verdict, type Base, type Outcome, type Rule, type SiteData, type Verdict } from "@/lib/rule";

const STATION_VARIANTS = VARIANTS.filter((v) => v.source === "station");
const OUTCOME_STATE: Record<Outcome, CellState> = { pay: "met", refund: "not", dispute: "dispute" };
const OUTCOME_TEXT: Record<Outcome, string> = { pay: "pays", refund: "refunds", dispute: "dispute" };

function verdictText(v: Verdict) {
  return v.state === "met" ? "rule met" : v.state === "not" ? "not met" : "no verdict";
}

function detail(v: Verdict, minSpell: number) {
  return (
    <div>
      <div className="tt-row">
        <span>Verdict</span>
        <b>{verdictText(v)}</b>
      </div>
      {v.longest !== null && (
        <div className="tt-row">
          <span>Longest hot spell</span>
          <b>
            {v.inBase ? v.longest.toFixed(1) : v.longest} days (need {minSpell})
          </b>
        </div>
      )}
      {v.share !== undefined && (
        <div className="tt-row">
          <span>Bootstrap replicates met</span>
          <b>{Math.round(v.share * 29)} of 29</b>
        </div>
      )}
      <div className="tt-row">
        <span>Summer days filled / missing</span>
        <b>
          {v.filled} / {v.missing}
        </b>
      </div>
      {v.why && <div className="note">{v.why}</div>}
      {v.inBase && <div className="note">Year inside the base period: bootstrapped (Zhang et al. 2005)</div>}
    </div>
  );
}

function outcomeDetail(o: ReturnType<typeof agreementOutcome>, rule: Rule) {
  return (
    <div>
      <div className="tt-row">
        <span>Agreement</span>
        <b>
          {o.outcome === "pay" ? "pays" : o.outcome === "refund" ? "refunds" : `dispute → ${rule.onDispute === "pay" ? "pays" : "refunds"} unless all three parties agree otherwise`}
        </b>
      </div>
      <div className="tt-row">
        <span>Provider A · station</span>
        <b>{verdictText(o.a)}</b>
      </div>
      <div className="tt-row">
        <span>Provider B · ERA5</span>
        <b>{verdictText(o.b)}</b>
      </div>
      {(o.a.why || o.b.why) && <div className="note">{o.a.why ?? o.b.why}</div>}
    </div>
  );
}

export function Designer({ d, rule, setRule, year, setYear, onReview, setSite, target, setTarget }: {
  d: SiteData; rule: Rule; setRule: (r: Rule) => void; year: number; setYear: (y: number) => void;
  onReview: () => void; setSite: (s: string) => void; target: number; setTarget: (t: number) => void;
}) {
  const years = d.years;
  const other: Base = rule.base === "1961-1990" ? "1991-2020" : "1961-1990";
  const sel = VARIANTS.find((v) => v.id === rule.variant)!;
  const outcomes = years.map((y) => agreementOutcome(d, rule, y));
  const rows: MatrixRow[] = [
    {
      id: "agreement",
      label: "Agreement (A+B)",
      selected: true,
      cells: outcomes.map((o) => ({ state: OUTCOME_STATE[o.outcome], detail: outcomeDetail(o, rule) })),
    },
    {
      id: rule.variant,
      label: `A · ${sel.short}`,
      cells: years.map((y) => {
        const v = verdict(d, rule, y);
        return { state: v.state, detail: detail(v, rule.minSpell) };
      }),
    },
    {
      id: "era5",
      label: "B · ERA5",
      cells: years.map((y) => {
        const v = verdict(d, { ...rule, variant: "era5" }, y);
        return { state: v.state, detail: detail(v, rule.minSpell) };
      }),
    },
    ...STATION_VARIANTS.filter((v) => v.id !== rule.variant).map((v) => ({
      id: v.id,
      label: `A if ${v.short}`,
      cells: years.map((y) => {
        const vd = verdict(d, { ...rule, variant: v.id }, y);
        return { state: vd.state, detail: detail(vd, rule.minSpell) };
      }),
    })),
    {
      id: "other-base",
      label: `Agreement, ${other}`,
      cells: years.map((y) => {
        const o = agreementOutcome(d, { ...rule, base: other }, y);
        return { state: OUTCOME_STATE[o.outcome], detail: outcomeDetail(o, { ...rule, base: other }) };
      }),
    },
  ];
  const flags = outcomes.map((o) => o.a.state !== "nodata" && o.b.state !== "nodata" && o.a.state !== o.b.state);
  const past = years.map((y, i) => [y, outcomes[i]] as const).filter(([y]) => y <= 2025);
  const pays = past.filter(([, o]) => o.outcome === "pay").map(([y]) => y);
  const refunds = past.filter(([, o]) => o.outcome === "refund").length;
  const disputes = past.filter(([, o]) => o.outcome === "dispute").map(([y]) => y);
  const disagree = past.filter(([, o]) => o.a.state !== "nodata" && o.b.state !== "nodata" && o.a.state !== o.b.state).length;
  const thin = disputes.length - disagree;

  const set = (p: Partial<Rule>) => setRule({ ...rule, ...p });
  const adopted = evaluate(d, rule, target);
  return (
    <div className="stack">
      <div className="card">
        <div className="field design-location">Community location
          <SitePicker site={d.site.id} setSite={setSite} label="Agreement location" />
        </div>
        <RuleFinder d={d} rule={rule} setRule={setRule} target={target} setTarget={setTarget} />
        <section className="design-part" aria-label="Adopted rule">
          <DesignStep n={3} title="The rule you will sign" />
          <p className="adopted">
            <strong>{definition(rule)}</strong>, June–September, {d.site.name}. Station gaps {sel.id === "station" ? "left empty" : `filled from ERA5 (${sel.short})`}, at most{" "}
            {rule.maxFilled} filled and {rule.maxMissing} missing; disputes not resolved by all three parties: {rule.onDispute === "pay" ? "pay the cooperative" : "refund the fund"}.{" "}
            <span className={onTarget(adopted, target) ? "chip good" : "chip warn"}>
              {onTarget(adopted, target) ? `meets your purpose: pays ${every(adopted.returnPeriod)}` : `pays ${every(adopted.returnPeriod)}, your purpose is 1 in ${target}`}
            </span>
          </p>
          <details className="design-settings">
            <summary>Adjust every setting</summary>
            <div className="controls">
          <div className="field">
            Provider A: station, gaps filled by
            <div className="seg" role="group" aria-label="Provider A gap filling">
              {STATION_VARIANTS.map((v) => (
                <button key={v.id} aria-pressed={rule.variant === v.id} onClick={() => set({ variant: v.id })} title={v.label}>
                  {v.id === "station" ? "nothing" : v.id === "station_qm" ? "quantile map" : v.id === "station_linear" ? "linear" : "raw ERA5"}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            Normal (base period)
            <div className="seg" role="group" aria-label="Base period">
              {(["1961-1990", "1991-2020"] as Base[]).map((b) => (
                <button key={b} aria-pressed={rule.base === b} onClick={() => set({ base: b })}>
                  {b.replace("-", "–")}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            Hot means above the
            <div className="seg" role="group" aria-label="Percentile">
              {([90, 95] as const).map((p) => (
                <button key={p} aria-pressed={rule.percentile === p} onClick={() => set({ percentile: p })}>
                  {p}th percentile
                </button>
              ))}
            </div>
          </div>
          <label className="field">
            For at least {rule.minSpell} days in a row
            <input type="range" min={3} max={10} value={rule.minSpell} onChange={(e) => set({ minSpell: +e.target.value })} />
          </label>
          <label className="field">
            Max days missing
            <input type="number" min={0} max={122} value={rule.maxMissing} onChange={(e) => set({ maxMissing: Math.max(0, Math.min(122, +e.target.value)) })} />
          </label>
          {rule.payout === "graded" && (() => {
            const steps = rule.steps ?? GRADED_STEPS;
            // Keep the ladder valid: days and shares rise, the last rung pays the whole deposit.
            const setStep = (i: number, part: 0 | 1, v: number) => {
              const next = steps.map((s) => [...s] as [number, number]);
              next[i][part] = v;
              const ok = next.every((s, k) => k === 0 || (s[0] > next[k - 1][0] && s[1] > next[k - 1][1])) && next[0][0] === 0 && next[next.length - 1][1] === 10000;
              if (ok) set({ steps: next });
            };
            return (
              <div className="field ladder-edit">
                Payout ladder (your own loss estimates)
                {steps.map(([d, b], i) => (
                  <span key={i}>
                    {rule.minSpell + d}+ days:{" "}
                    {i > 0 && <input type="number" min={1} max={20} value={d} aria-label={`Rung ${i + 1}: days beyond the minimum`} onChange={(e) => setStep(i, 0, +e.target.value)} />}
                    {i > 0 && " days beyond the minimum, "}
                    {i < steps.length - 1
                      ? <input type="number" min={5} max={95} step={5} value={b / 100} aria-label={`Rung ${i + 1}: percent of the deposit`} onChange={(e) => setStep(i, 1, Math.round(+e.target.value * 100))} />
                      : <b>100</b>}% of the deposit
                  </span>
                ))}
              </div>
            );
          })()}
          <label className="field">
            Max days filled
            <input type="number" min={0} max={122} value={rule.maxFilled} onChange={(e) => set({ maxFilled: Math.max(0, Math.min(122, +e.target.value)) })} />
          </label>
            </div>
          </details>
        </section>
        <section className="design-part" aria-label="Check the consequences">
          <DesignStep n={4} title="Check the consequences, summer by summer" />
        <DecisionReview d={d} rule={rule} setRule={setRule} year={year} setYear={setYear} onReview={onReview} />
        </section>
        <details className="historical-detail"><summary>Inspect all 61 summers, the alternative gap rules and full-history counts</summary>
        <p className="note" style={{ marginBottom: 10 }}>
          Season 1 June – 30 September in {d.site.name}. The agreement needs <strong>both</strong> providers to agree: provider A computes from the weather
          station (gaps filled as chosen), provider B from ERA5. The top row is what the agreement would have done each summer; the rows below show why.
        </p>
        <Matrix
          years={years}
          rows={rows}
          flags={flags}
          flagLabel="A and B disagree that summer"
          ariaLabel={`Backtest of the agreement in ${d.site.name}, 1966–2026`}
          onPick={(id) => STATION_VARIANTS.some((v) => v.id === id) && set({ variant: id as Rule["variant"] })}
        />
        <p className="callout blue" id="ai-test" style={{ marginTop: 12 }}>
          <strong>Why quantile mapping is the default gap fill.</strong> In a test fixed before we saw results, we erased real station summers and filled them
          back. A machine-learning model (LightGBM) had the lowest average error but missed 3 of 9 heatwaves, because it pulls hot days toward typical ones;
          quantile mapping kept the hot tail and got all 9 right. So the AI was not adopted. The evidence is small: 3 complete summers.
        </p>
        <div className="grid-3" style={{ marginTop: 12 }}>
        <div className="fact">
          <div className="big">
            {pays.length} of {past.length}
          </div>
          <div className="small">
            summers 1966–2025 in which both providers agree and the agreement pays{pays.length ? `, most recently ${pays.slice(-6).join(", ")}` : ""}.
            {` ${refunds} would refund.`}
          </div>
        </div>
        <div className="fact">
          <div className="big">{disputes.length} disputes</div>
          <div className="small">
            {disagree} where the providers disagree and {thin} where one has no verdict (too little data){disputes.length ? `, e.g. ${disputes.slice(-5).join(", ")}` : ""}.
            Each ends by a unanimous decision of the three parties, or else by the signed fallback: <strong>{rule.onDispute === "pay" ? "pay out" : "refund"}</strong>.
          </div>
        </div>
        <div className="fact">
          <div className="big">{OUTCOME_TEXT[outcomes[years.indexOf(2024)]?.outcome ?? "dispute"]}</div>
          <div className="small">
            what this agreement would do for summer 2024 in {d.site.name}.
          </div>
        </div>
        </div>
        </details>
      </div>
    </div>
  );
}
