"use client";
import { useEffect, useState } from "react";
import { Agreement, type Scenario } from "./Agreement";
import { Designer } from "./Designer";
import { RECORDED_CASES, RecordedRuns } from "./RecordedRuns";
import { RegionScan } from "./RegionScan";
import { HowItWorks } from "./HowItWorks";
import { COUNTRY, FEATURED, IN_TURKIYE, SITES } from "@/lib/sites";
import { Story } from "./Story";
import { STATIC_EDITION, asset } from "@/lib/edition";
import { compareSeason, ruleFromSpec } from "@/lib/comparison";
import { ladderOf, type Rule, type SiteData } from "@/lib/rule";

const DEFAULT_RULE: Rule = { variant: "station_qm", base: "1991-2020", percentile: 90, minSpell: 6, maxMissing: 0, maxFilled: 122, onDispute: "refund", payout: "graded" };

const CASES: { label: string; blurb: string; site: string; year: number; rule: Partial<Rule>; recorded: string }[] = [
  { label: "A heatwave that pays", blurb: "Antalya 2024 · both records see a 13-day spell by mid-June · paid in June, not October", site: "antalya", year: 2024, rule: {}, recorded: "heatwave-pays" },
  { label: "Sources disagree", blurb: "Muğla 2021 · station 4 days, ERA5 10 · 15,000 back at once, only 35,000 disputed", site: "mugla", year: 2021, rule: {}, recorded: "sources-disagree" },
  {
    label: "Too little data",
    blurb: "Antalya 2023 · rule allows 60 filled days, station needs 72 · provider abstains · fallback pays",
    site: "antalya",
    year: 2023,
    rule: { maxFilled: 60, onDispute: "pay" },
    recorded: "too-little-data",
  },
];

function ThemeToggle() {
  const [t, setT] = useState<string | null>(null);
  useEffect(() => {
    try {
      const s = localStorage.getItem("ep-theme");
      if (s) {
        document.documentElement.dataset.theme = s;
        setT(s);
      }
    } catch {
      /* storage unavailable */
    }
  }, []);
  const next = () => {
    const dark = t ? t === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    const v = dark ? "light" : "dark";
    document.documentElement.dataset.theme = v;
    setT(v);
    try {
      localStorage.setItem("ep-theme", v);
    } catch {
      /* ignore */
    }
  };
  return (
    <button className="theme-toggle" onClick={next} aria-label="Toggle dark mode">
      ◐ theme
    </button>
  );
}

function openAiTest(e: React.MouseEvent) {
  const target = document.getElementById("ai-test");
  const details = target?.closest("details");
  if (!target || !details) return;
  e.preventDefault();
  details.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
}

/** The default disagreement, computed from the pinned data rather than written into the page. */
function HeroCase({ d, onDecide }: { d: SiteData; onDecide: () => void }) {
  const s = compareSeason(d, DEFAULT_RULE, 2021);
  const flat = compareSeason(d, { ...DEFAULT_RULE, payout: "flat" }, 2021).policies.dual;
  const ladder = ladderOf(DEFAULT_RULE);
  const rows = [
    { name: "Muğla weather station", v: s.a.longest ?? 0, cls: "station" },
    { name: "ERA5 reanalysis", v: s.b.longest ?? 0, cls: "era5" },
  ];
  const scale = Math.max(ladder[ladder.length - 1][0], ...rows.map((r) => r.v)) + 2;
  const p = s.policies.dual;
  const total = p.paidNowCents + p.contestedCents + p.refundedNowCents;
  const parts = [
    { cls: "paid", label: "paid at once", cents: p.paidNowCents },
    { cls: "held", label: "in dispute", cents: p.contestedCents },
    { cls: "back", label: "back to the fund at once", cents: p.refundedNowCents },
  ].filter((x) => x.cents > 0);
  const demo = (c: number) => (c / 100).toLocaleString("en-US");
  return (
    <figure className="hero-case" aria-label="Muğla, summer 2021: the two records disagree">
      <figcaption>
        <span className="eyebrow">Muğla · summer 2021</span>
        <strong>Longest run of unusually hot days</strong>
      </figcaption>
      <div className="spell-bars">
        {rows.map((r) => (
          <div key={r.cls} className="spell-row">
            <span>{r.name}</span>
            <div className="spell-track">
              <i className={`spell-fill ${r.cls}`} style={{ width: `${(r.v / scale) * 100}%` }} />
              {ladder.map(([days]) => <i key={days} className="spell-need" style={{ left: `${(days / scale) * 100}%` }} />)}
            </div>
            <b>{r.v} days</b>
          </div>
        ))}
        <div className="spell-legend">
          {ladder.map(([days, bps]) => <span key={days} style={{ left: `${(days / scale) * 100}%` }}>{bps / 100}%</span>)}
        </div>
      </div>
      <div className="deposit" aria-label={`The ${demo(total)} DEMO deposit after the season`}>
        <div className="deposit-bar">
          {parts.map((x) => <i key={x.cls} className={x.cls} style={{ width: `${(x.cents / total) * 100}%` }} />)}
        </div>
        <div className="deposit-key">
          {parts.map((x) => <span key={x.cls}><i className={x.cls} />{demo(x.cents)} {x.label}</span>)}
        </div>
      </div>
      <p>
        The deposit pays more for a longer heatwave. The station supports nothing, ERA5 supports 70%, so the 30% neither supports goes back at once and
        only the difference, <strong>{demo(p.contestedCents)} DEMO</strong>, is in question. All or nothing would put all {demo(flat.contestedCents)} in dispute.
      </p>
      <p className="note">
        That summer, forest fires burned across Muğla and Antalya in heat above 40 °C
        (<a href="https://earthobservatory.nasa.gov/images/148650/fires-rage-in-turkey" target="_blank" rel="noreferrer">NASA</a>). This rule pays on heat, not fire.
      </p>
      <a className="btn" href="#design" onClick={onDecide}>Decide this case →</a>
    </figure>
  );
}

export function App() {
  const [data, setData] = useState<Record<string, SiteData> | null>(null);
  const [site, setSite] = useState("mugla");
  const [rule, setRule] = useState<Rule>(DEFAULT_RULE);
  const [year, setYear] = useState(2021);
  // How often the agreement should pay (1 summer in N); signed with the rule as its purpose.
  const [target, setTarget] = useState(5);
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [recorded, setRecorded] = useState(RECORDED_CASES[1].id);
  const showRecorded = (id: string) => { setRecorded(id); document.getElementById("lock")?.scrollIntoView({ behavior: "smooth" }); };
  const runCase = (c: (typeof CASES)[number]) => {
    setSite(c.site);
    setRule({ ...DEFAULT_RULE, ...c.rule });
    setYear(c.year);
    if (STATIC_EDITION) showRecorded(c.recorded);
    else setScenario({ nonce: Date.now(), label: c.label, readyMade: true });
  };
  const [err, setErr] = useState<string | null>(null);
  const load = (ids: string[]) =>
    Promise.all(ids.map((s) => fetch(asset(`/data/${s}.json`)).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${s}: ${r.status}`))))))
      .then((rows: SiteData[]) => setData((cur) => ({ ...cur, ...Object.fromEntries(rows.map((d) => [d.site.id, d])) })));
  useEffect(() => {
    // The worked examples first; the other stations follow for the regional scan.
    load(FEATURED)
      .then(() => load(SITES.filter((s) => !s.featured).map((s) => s.id)))
      .catch((e) => setErr(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const chooseSite = (id: string) => {
    if (data?.[id]) setSite(id);
    else load([id]).then(() => setSite(id)).catch((e) => setErr(String(e)));
  };

  return (
    <>
      <header className="topbar">
        <div className="wrap">
          <div className="brand">
            <span className="brand-mark" aria-hidden />
            ExtremeProof
          </div>
          <nav className="steps" aria-label="Steps">
            <a href="#how">How</a>
            <a href="#normal">1 Climate</a>
            <a href="#design">2 Rule</a>
            <a href="#lock">3 Lock</a>
            <a href="#replay">4 Season</a>
            <a href="#attack">5 Attack</a>
            <a href="#verify">6 Verify</a>
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main>
        <div className="wrap hero">
          <div className="hero-grid">
            <div>
              <div className="eyebrow">Climate data verification · {SITES.length} stations in {new Set(SITES.map((s) => s.country)).size} countries</div>
              <h1>Two weather records disagree. Who decides the heat relief?</h1>
              <p className="lede">
                A relief fund and a farmers' cooperative fix the rule before summer. As the heat builds, the part of the payment both
                records already support is released at the next weekly check after publication; only the difference is ever disputed, and anyone can recheck every step.
              </p>
              <p className="hero-stat">
                <strong>96%</strong> of the relief both records agreed on would have been available to the cooperative before the season ended — replaying 2021–2025 at {IN_TURKIYE.length} stations
                in Türkiye.
              </p>
              <div className="hero-action"><a className="btn" href="#design">Decide a real disagreement →</a></div>
            </div>
            {data && <HeroCase d={data.mugla} onDecide={() => { setSite("mugla"); setRule(DEFAULT_RULE); setYear(2021); }} />}
          </div>
          <dl className="status-row" aria-label="What is real, executed and simulated">
            <div><dt>Real</dt><dd>GHCN-Daily station and ERA5 records at {SITES.length} stations in {[...new Set(SITES.map((s) => COUNTRY[s.country]))].join(", ")}, 1966–2025; engine cross-checked with xclim</dd></div>
            <div><dt>Executed</dt><dd>Solidity contract that counts the heatwave itself from daily readings posted on chain, releases money during it and disputes only the providers' difference; standalone verifier</dd></div>
            <div><dt>AI tested</dt><dd>LightGBM gap filling missed 3 of 9 heatwaves, so it was not adopted. <a href="#ai-test" onClick={openAiTest}>See the test</a></dd></div>
            <div className="sim"><dt>Simulated</dt><dd>Fund, cooperative, checker, DEMO money, chain clock</dd></div>
          </dl>
          {data && (<>
            <h2 className="cases-title">{STATIC_EDITION ? "Or open a recorded run: sign, settle, attack, verify" : "Or run a full agreement in about two minutes"}</h2>
            <div className="cases" aria-label="Ready-made cases">
              {CASES.map((c) => (
                <button key={c.label} className="case" onClick={() => runCase(c)}>
                  <strong>{c.label} →</strong>
                  <span>{c.blurb}</span>
                </button>
              ))}
            </div>
          </>)}
          <p className="note" style={{ marginTop: 8 }}>
            {STATIC_EDITION
              ? "Each case shows a run recorded from the real contract and provider services, with a bundle you can verify yourself."
              : "Each case signs a real agreement on the local chain and plays the whole summer: weekly releases, both providers' reports, one cheating attempt the contract refuses, and the settlement. Then try the other attacks in step 5 and run the verifier in step 6."}
          </p>
        </div>
        <HowItWorks />
        {err && <p className="wrap err">Could not load data: {err}</p>}
        {data && (
          <>
            <section className="step" id="normal">
              <div className="wrap">
                <div className="step-head">
                  <span className="step-num">1</span>
                  <h2>What counts as unusually hot here</h2>
                  <p>
                    An extreme is only extreme relative to a place's climate — its 30-year statistics. Change the 30 years, or the thermometer, and the same summer can
                    count or not.
                  </p>
                </div>
                <Story data={data} site={site} setSite={chooseSite} />
              </div>
            </section>
            <section className="step" id="design">
              <div className="wrap">
                <div className="step-head">
                  <span className="step-num">2</span>
                  <h2>Design the rule before anyone signs</h2>
                  <p>
                    Say how often the community should be paid, compare complete rules that do it, adopt one and check what it would have done each summer.
                    Then the fund, the cooperative and the checker sign it in step 3.
                  </p>
                </div>
                <Designer d={data[site]} rule={rule} setRule={setRule} year={year} setYear={setYear} setSite={chooseSite} target={target} setTarget={setTarget}
                  onReview={() => STATIC_EDITION
                    ? showRecorded(CASES.find((c) => c.site === site && c.year === year)?.recorded ?? recorded)
                    : setScenario({ nonce: Date.now(), label: `${data[site].site.name} ${year} decision review` })} />
                <details className="historical-detail region-detail">
                  <summary>The same rule at all {SITES.length} stations: where the record decides the payment</summary>
                  <RegionScan data={data} rule={rule} site={site} setSite={chooseSite} />
                </details>
              </div>
            </section>
            {STATIC_EDITION
              ? <RecordedRuns selected={recorded} setSelected={setRecorded} data={data} />
              : <Agreement data={data} site={site} rule={rule} target={target} year={year} setYear={setYear} scenario={scenario}
                  onRestore={(spec, savedTarget) => { setSite(spec.site.id); setRule(ruleFromSpec(spec)); setYear(spec.observation_year); setTarget(spec.purpose?.target_return_period_summers ?? savedTarget); }} />}
          </>
        )}
      </main>
      <footer className="footer">
        <div className="wrap grid-3">
          <div>
            <h3>Data and licences</h3>
            <ul>
              <li>
                Station data: NOAA NCEI GHCN-Daily (Menne et al. 2012, doi:10.7289/V5D21VHZ). Citation requested; no use restrictions stated.
              </li>
              <li>Reanalysis: ERA5 via Open-Meteo (CC BY 4.0, non-commercial free tier). Weather data by Open-Meteo.com; Copernicus Climate Change Service.</li>
              <li>Index definitions: ETCCDI; bootstrap after Zhang et al. (2005); percentiles cross-checked with xclim.</li>
            </ul>
          </div>
          <div>
            <h3>What is simulated</h3>
            <ul>
              <li>The fund, cooperative, checker and both data providers run on this machine with demo keys.</li>
              <li>DEMO units are not money. The chain clock is moved forward to replay a past summer.</li>
              <li>This prototype supports adaptation agreements. It does not measure emissions reductions or avoided losses; release timing is replayed from past data, not observed in a real scheme.</li>
            </ul>
          </div>
          <div>
            <h3>Limits we state openly</h3>
            <ul>
              <li>A blockchain does not make data true. If every source is wrong, the payout is wrong.</li>
              <li>Station records are not homogenised; ERA5 before ~1979 has fewer observations.</li>
              <li>Provider A fills station gaps with ERA5, provider B's source, so the two are not fully independent observations.</li>
              <li>Scope: observed heat only. Money is released once published data show a qualifying spell (about a week behind the heat), never on a forecast.</li>
            </ul>
          </div>
        </div>
      </footer>
    </>
  );
}
