"use client";
import { useEffect, useState } from "react";
import { asset } from "@/lib/edition";
import { Ledger, type LogEntry } from "./Ledger";
import { canonicalJson, sha256Hex } from "@/lib/chain";
import { memberSheet } from "@/lib/memberSheet";
import { purposeText } from "@/lib/finder";
import { ladderText, type SiteData } from "@/lib/rule";

// Steps 3–6 of the static edition: runs recorded from the real local stack by
// scripts/record-runs.mjs. Nothing here is computed or typed in by hand.
interface Check { check: string; ok: boolean; detail?: string }
interface Run {
  id: string;
  agreement: number;
  spec: any;
  log: LogEntry[];
  contractRefusal: string;
  status: string;
  outcome: string | null;
  verifier: { live: { passed: boolean; checks: Check[] }; offline: { passed: boolean; checks: Check[] } };
  tampered: { kind: string; what: string; passed: boolean; failed: string[] }[];
  bundle: { file: string; sha256: string; bytes: number };
}
interface Index { recorded_at: string; chain: { id: number; contract: string }; cases: { id: string; title: string }[] }

export const RECORDED_CASES: { id: string; label: string }[] = [
  { id: "heatwave-pays", label: "Antalya 2024 · paid in June" },
  { id: "sources-disagree", label: "Muğla 2021 · only the difference disputed" },
  { id: "too-little-data", label: "Antalya 2023 · too little data" },
];

const TAMPER_LABEL: Record<string, string> = {
  spec_base_period: "Change the normal after the heatwave",
  observation: "Edit one temperature reading",
  evidence_outcome: "Flip a provider's published verdict",
  drop_evidence: "Hand over the bundle without the providers' evidence",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (mmdd: string) => `${Number(mmdd.slice(3))} ${MONTHS[Number(mmdd.slice(0, 2)) - 1]}`;

function StepHead({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return <div className="step-head"><span className="step-num">{n}</span><h2>{title}</h2><p>{children}</p></div>;
}

export function RecordedRuns({ selected, setSelected, data }: { selected: string; setSelected: (id: string) => void; data: Record<string, SiteData> }) {
  const [index, setIndex] = useState<Index | null>(null);
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(asset("/recorded/index.json")).then((r) => r.json()).then(setIndex).catch((e) => setErr(String(e)));
    Promise.all(RECORDED_CASES.map((c) => fetch(asset(`/recorded/${c.id}.json`)).then((r) => r.json())))
      .then((all: Run[]) => setRuns(Object.fromEntries(all.map((r) => [r.id, r]))))
      .catch((e) => setErr(String(e)));
  }, []);
  const run = runs[selected];
  if (err) return <p className="wrap err">Could not load the recorded runs: {err}</p>;
  if (!run || !index) return <div className="wrap card note">Loading recorded runs…</div>;
  const s = run.spec;
  const offline = run.verifier.offline.checks;
  const live = run.verifier.live.checks;
  const recorded = index.recorded_at.slice(0, 10);

  return (
    <>
      <section className="step" id="lock">
        <div className="wrap">
          <StepHead n={3} title="A real run, recorded">
            This public page has no live chain. Steps 1–2 above run in your browser. Steps 3–6 replay agreements recorded on {recorded} from the full local
            stack: Solidity contract, two provider services and the verifier. Parties and DEMO money are simulated. Download a bundle in step 6 and check it yourself.
          </StepHead>
          <div className="seg recorded-tabs" role="group" aria-label="Recorded case">
            {RECORDED_CASES.map((c) => (
              <button key={c.id} aria-pressed={c.id === selected} onClick={() => setSelected(c.id)}>{c.label}</button>
            ))}
          </div>
          <div className="card stack recorded-rule">
            <strong>{s.title}</strong>
            <dl className="kv">
              <dt>Rule</dt>
              <dd>{day(s.rule.season[0])}–{day(s.rule.season[1])} {s.observation_year}: at least {s.rule.min_spell_days} days in a row above the {s.rule.percentile}th percentile of {s.rule.base_period[0].slice(0, 4)}–{s.rule.base_period[1].slice(0, 4)}</dd>
              <dt>Providers</dt>
              <dd>A: station {s.site.station}, at most {s.rule.max_filled_days} days filled · B: ERA5 reanalysis</dd>
              <dt>Payment</dt>
              <dd>{ladderText(s.settlement.payout_ladder)} of {(s.settlement.amount_cents / 100).toLocaleString("en-US")} DEMO; the share both providers' readings support is paid, only the difference is disputed → {s.settlement.on_dispute === "pay" ? "pay out" : "refund"}</dd>
              <dt>Thresholds</dt>
              <dd>{s.sources.map((x: any) => `${x.id === "station" ? "station" : "ERA5"}: ${x.season_normal_mdegc ? `${x.season_normal_mdegc.length} daily thresholds signed` : "no normal (abstains)"}`).join(" · ")}; the contract checks every posted reading against them</dd>
              {s.purpose && <><dt>Purpose</dt><dd>{purposeText(s.purpose)}</dd></>}
              <dt>Contract</dt>
              <dd className="mono">chain {index.chain.id} · {index.chain.contract} · agreement #{run.agreement}</dd>
            </dl>
            <div className="btn-row">
              <button className="btn ghost" onClick={async () => {
                const url = URL.createObjectURL(new Blob([memberSheet(s, await sha256Hex(canonicalJson(s)), data[s.site.id])], { type: "text/html" }));
                const a = document.createElement("a"); a.href = url; a.download = `extremeproof-${s.site.id}-${s.observation_year}-member-summary.html`; a.click(); URL.revokeObjectURL(url);
              }}>Download a summary for members (EN/TR)</button>
              <span className="note">Plain-language page the cooperative can read before its representative signs.</span>
            </div>
          </div>
        </div>
      </section>
      <section className="step" id="replay">
        <div className="wrap">
          <StepHead n={4} title="What happened, in chain time">
            The chain clock was moved through the season. Each line was written by the page while the real contract and provider services ran.
          </StepHead>
          <div className="card">
            <Ledger entries={run.log} contract={index.chain.contract} chainId={index.chain.id} />
          </div>
          {run.outcome && <p className="recorded-outcome"><span className="chip good">Final</span> {run.outcome}</p>}
        </div>
      </section>
      <section className="step" id="attack">
        <div className="wrap">
          <StepHead n={5} title="Try to cheat: each attempt was run for real">
            The contract and the standalone verifier were given altered inputs. Every altered bundle failed.
          </StepHead>
          <ul className="recorded-attacks">
            <li><span className="chip bad">contract refused</span><span><strong>Re-sign the rule with another normal after the season.</strong> {run.contractRefusal}</span></li>
            {run.tampered.map((t) => (
              <li key={t.kind}>
                <span className={`chip ${t.passed ? "good" : "bad"}`}>{t.passed ? "not detected" : `${t.failed.length} checks failed`}</span>
                <span><strong>{TAMPER_LABEL[t.kind] ?? t.kind}.</strong> {t.what} <span className="note">Failed: {t.failed.join(", ")}.</span></span>
              </li>
            ))}
          </ul>
        </div>
      </section>
      <section className="step" id="verify">
        <div className="wrap">
          <StepHead n={6} title="Check it yourself, without trusting us">
            Download the bundle and the verifier: one Python file, standard library only, sharing no code with the providers. It recomputes percentiles, gap filling
            and hot spells from the raw files and checks the recorded settlement.
          </StepHead>
          <div className="grid-2">
            <div className="card stack">
              <div className="btn-row">
                <a className="btn" href={asset(`/recorded/${run.bundle.file}`)} download>Download bundle (.zip, {Math.round(run.bundle.bytes / 1024)} KB)</a>
                <a className="btn ghost" href={asset("/recorded/verify.py")} download>Download verify.py</a>
              </div>
              <pre className="spec">python verify.py {run.bundle.file}</pre>
              <p className="note breakable">
                Expected: {offline.filter((c) => c.ok).length}/{offline.length} checks passed. SHA-256 of the bundle: <span className="mono">{run.bundle.sha256}</span>.
                With the local stack running, <span className="mono">--rpc http://127.0.0.1:8545</span> also re-reads the chain; at recording time that gave{" "}
                {live.filter((c) => c.ok).length}/{live.length}.
              </p>
            </div>
            <div className="card">
              <strong>Offline checks in this bundle</strong>
              <ul className="recorded-checks">
                {offline.map((c, i) => <li key={i}><span className={`chip ${c.ok ? "good" : "bad"}`}>{c.ok ? "pass" : "fail"}</span> {c.check}</li>)}
              </ul>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
