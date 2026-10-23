"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Hex } from "viem";
import { LineChart, type Band } from "./charts";
import { Ledger } from "./Ledger";
import { memberSheet } from "@/lib/memberSheet";
import { purposeBlock, purposeText } from "@/lib/finder";
import { asset } from "@/lib/edition";
import {
  DAY,
  HUB,
  call,
  canonicalJson,
  chainTime,
  fmtChainDate,
  fmtDemo,
  hub,
  publicClient,
  readAgreement,
  receiptInfo,
  revertName,
  seasonTiming,
  sha256Bytes,
  sha256Hex,
  termMismatches,
  tokenBalance,
  txInfo,
  warpTo,
  write,
  type AgreementView,
  type Deployment,
  type TxInfo,
} from "@/lib/chain";
import { VARIANTS, dayIndex, doy, ladderText, seasonDates, type Rule, type SiteData } from "@/lib/rule";
import { SignedDecisionReview } from "./DecisionReview";

type Src = "station" | "era5";
interface ProviderState {
  report?: { verdict: number; outcome: boolean | null; reason: string; longest_spell: number; days_posted?: number; evidence_digest: string; report_tx?: string };
  evidence?: any;
  error?: string;
}
interface Check {
  check: string;
  ok: boolean;
  detail: string;
}
interface VerifyResult {
  tamper: string;
  what_was_changed: string;
  passed: boolean;
  checks: Check[];
}
interface Draft {
  spec: any;
  hash: Hex;
  browserHash: Hex;
  key: string;
}
export interface Scenario {
  nonce: number;
  label: string;
  /** A ready-made case: nobody chose a payment frequency, so no purpose block is signed. */
  readyMade?: boolean;
}

export const SEASONS = [2021, 2022, 2023, 2024, 2025, 2026];
const PARTY_INFO: Record<string, { name: string; role: string }> = {
  funder: { name: "Relief fund", role: "Funder · deposits the money" },
  community: { name: "Farmers' cooperative", role: "Represents the people the money is for" },
  checker: { name: "Independent checker", role: "Reviews the rule before it is locked" },
};
const ROLE_BIT: Record<string, number> = { funder: 1, community: 2, checker: 4 };
const REASON_TEXT: Record<string, string> = {
  too_many_missing_days_in_season: "too many missing days in the season",
  too_many_filled_days_in_season: "more filled days than the agreed limit",
  base_period_coverage_below_agreed_minimum: "base period has too little data",
};
const FILL_TEXT: Record<string, string> = {
  none: "not filled (missing days break a spell)",
  era5_quantile_map: "quantile-mapped ERA5",
  era5_monthly_linear: "linear-corrected ERA5",
  era5_raw: "raw ERA5",
};

function Checks({ res }: { res: VerifyResult }) {
  const failed = res.checks.filter((c) => !c.ok);
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div>
        {res.passed ? (
          <span className="chip good">✓ all {res.checks.length} checks passed</span>
        ) : (
          <span className="chip bad">✕ {failed.length} of {res.checks.length} checks failed</span>
        )}
      </div>
      {res.tamper !== "none" && <p className="note">What was changed: {res.what_was_changed}</p>}
      <ul className="checks">
        {(res.passed ? res.checks : failed.concat(res.checks.filter((c) => c.ok).slice(0, 2))).map((c, i) => (
          <li key={i}>
            <span className={c.ok ? "mark-ok" : "mark-bad"} aria-label={c.ok ? "pass" : "fail"}>
              {c.ok ? "✓" : "✕"}
            </span>
            <span>
              {c.check}
              {!c.ok && c.detail ? <span className="note"> — {c.detail}</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const normalRange = (n: number[]) => {
  const c = n.filter((x) => x < 2 ** 31 - 1).map((x) => x / 1000);
  return `${Math.min(...c).toFixed(1)}–${Math.max(...c).toFixed(1)} °C`;
};

/** Human summary of a signed spec (what the parties actually agreed). */
function SpecSummary({ spec, data }: { spec: any; data: Record<string, SiteData> }) {
  const r = spec.rule;
  const st = spec.settlement;
  const d = data[spec.site.id];
  const fill = spec.sources.find((s: any) => s.id === "station")?.fill?.method ?? "none";
  return (
    <><SignedDecisionReview spec={spec} data={data} /><dl className="kv">
      <dt>Place</dt>
      <dd>
        {spec.site.name} · station {spec.site.station}
        {d ? ` and the ERA5 grid cell at ${d.era5_grid.lat}°N ${d.era5_grid.lon}°E` : ""}
      </dd>
      <dt>Rule</dt>
      <dd>
        1 Jun–30 Sep {spec.observation_year}: at least {r.min_spell_days} days in a row above the {r.percentile}th percentile of{" "}
        {r.base_period[0].slice(0, 4)}–{r.base_period[1].slice(0, 4)}
      </dd>
      <dt>Provider A</dt>
      <dd>
        Station, gaps {FILL_TEXT[fill]}; abstains if more than {r.max_missing_days} days missing or {r.max_filled_days} filled
      </dd>
      <dt>Provider B</dt>
      <dd>ERA5 reanalysis (provider A's gap filling also uses ERA5, so A and B are not fully independent)</dd>
      <dt>Data</dt>
      <dd>
        Pinned now: both records up to 31 Dec {spec.observation_year - 1} (normal and gap-fill fit), by fingerprint. Not yet existing: {spec.observation_year},
        to be fetched from {spec.sources.map((s: any) => s.season_data.publisher).join(" and ")}; each provider posts the season's daily readings on chain
        with the fingerprint of exactly what it fetched.
      </dd>
      <dt>“Unusually hot”, day by day</dt>
      <dd>
        {spec.sources.map((s: any) => s.season_normal_mdegc
          ? `${s.id === "station" ? "Station" : "ERA5"}: ${s.season_normal_mdegc.length} daily thresholds, ${normalRange(s.season_normal_mdegc)}`
          : `${s.id === "station" ? "Station" : "ERA5"}: no normal (too little base-period data), so it can only abstain`).join(" · ")}.
        Signed now; the contract stores their fingerprint and compares every posted reading with them.
      </dd>
      <dt>Payout</dt>
      <dd>
        {ladderText(st.payout_ladder)} of {fmtDemo(BigInt(st.amount_cents))}. The share both providers' readings support is paid as soon as they show it, during the season if the heat comes early; after it the
        share neither supports returns to the fund; only the difference is disputed → unanimous vote of the three parties, or after 30 days{" "}
        <strong>{st.on_dispute === "pay" ? "paid out" : "refunded"}</strong>
      </dd>
      {spec.purpose && (
        <>
          <dt>Purpose</dt>
          <dd>{purposeText(spec.purpose)}</dd>
        </>
      )}
      <dt>Contract windows</dt>
      <dd>
        lock before {fmtChainDate(st.timing.window_start).slice(0, 10)}; readings for days that have ended during the season; the final post per
        provider from {fmtChainDate(st.timing.window_end).slice(0, 10)} to {fmtChainDate(st.timing.report_deadline).slice(0, 10)}
      </dd>
    </dl></>
  );
}

export function Agreement({
  data,
  site,
  rule,
  target,
  year,
  setYear,
  scenario,
}: {
  data: Record<string, SiteData>;
  site: string;
  rule: Rule;
  target: number;
  year: number;
  setYear: (y: number) => void;
  scenario: Scenario | null;
}) {
  const [dep, setDep] = useState<Deployment | null>(null);
  const [offline, setOffline] = useState<string | null>(null);
  const [now, setNow] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [id, setId] = useState<bigint | null>(null);
  const [ag, setAg] = useState<AgreementView | null>(null);
  const [prov, setProv] = useState<Record<Src, ProviderState>>({ station: {}, era5: {} });
  const [attack, setAttack] = useState<{ provider?: any; changeRule?: string }>({});
  const [tamper, setTamper] = useState<Record<string, VerifyResult>>({});
  const [verified, setVerified] = useState<VerifyResult | null>(null);
  const [bal, setBal] = useState<{ funder: bigint; beneficiary: bigint; escrow: bigint } | null>(null);
  const [log, setLog] = useState<{ t: number; text: string; tx?: TxInfo }[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [interimDone, setInterimDone] = useState(false);
  const [releases, setReleases] = useState<{ date: string; amount: bigint }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  // Settings a ready-made case wrote. A case demonstrates settlement; nobody chose a
  // payment frequency for it, so its rule is signed without a purpose block.
  const caseKey = useRef<string | null>(null);

  const stationFill = VARIANTS.find((v) => v.id === rule.variant)?.fill ?? "era5_quantile_map";
  // Everything that goes into the rule text. Any change invalidates an unproposed draft.
  const draftKey = JSON.stringify({ site, year, rule, stationFill, target });
  // Once proposed, the signed spec is the only source of truth for steps 3-6.
  const spec = draft?.spec ?? null;
  const fixed = id !== null && spec !== null;
  const d = fixed ? data[spec.site.id] : data[site];
  const seasonYear: number = fixed ? spec.observation_year : year;

  const refresh = useCallback(async () => {
    if (!dep) return;
    setNow(await chainTime());
    if (id !== null) setAg(await readAgreement(dep, id));
    setBal({
      funder: await tokenBalance(dep, dep.roles.funder),
      beneficiary: await tokenBalance(dep, dep.roles.beneficiary),
      escrow: await tokenBalance(dep, dep.TriggerAgreement),
    });
  }, [dep, id]);

  useEffect(() => {
    hub<Deployment>("/api/deployment")
      .then((x) => {
        if (x.providers.some((p) => p.error)) throw new Error("a provider service is not reachable");
        setDep(x);
      })
      .catch((e) => setOffline(String(e.message ?? e)));
  }, []);
  useEffect(() => {
    refresh().catch(() => undefined);
  }, [refresh]);

  // A draft that no longer matches the settings on screen must not be proposed.
  useEffect(() => {
    if (draft && id === null && draft.key !== draftKey) {
      setDraft(null);
      setNotice("Settings changed after the rule was written, so the draft was discarded. Write the rule again.");
    }
  }, [draftKey, draft, id]);

  const addLog = async (text: string, tx?: TxInfo) => {
    const t = await chainTime().catch(() => now);
    setLog((l) => [...l, { t, text, tx }]);
  };

  const run = async (name: string, f: () => Promise<void>) => {
    setBusy(name);
    setErr(null);
    try {
      await f();
    } catch (e: any) {
      setErr(revertName(e));
    } finally {
      setBusy(null);
      await refresh().catch(() => undefined);
    }
  };

  const available = SEASONS.filter((y) => seasonTiming(y).windowStart > now);

  const clearAgreement = () => {
    if (timer.current) clearInterval(timer.current);
    setPlaying(false);
    setDraft(null);
    setId(null);
    setAg(null);
    setProv({ station: {}, era5: {} });
    setInterimDone(false);
    setReleases([]);
    setAttack({});
    setTamper({});
    setVerified(null);
    setIdx(0);
    setLog([]);
    setErr(null);
  };

  const writeRule = async () => {
    // The purpose and the calibration the parties saw, from the same pinned table the page uses.
    const table = await fetch(asset(`/data/${site}.json`)).then((x) => x.arrayBuffer());
    const purpose = caseKey.current === draftKey ? null : purposeBlock(data[site], rule, target, (await sha256Bytes(table)).slice(2));
    const r = await hub<{ spec: any; hash: Hex }>("/api/spec-template", {
      purpose,
      site,
      year,
      base: rule.base,
      percentile: rule.percentile,
      min_spell_days: rule.minSpell,
      fill_method: stationFill,
      max_missing_days: rule.maxMissing,
      max_filled_days: rule.maxFilled,
      on_dispute: rule.onDispute,
      payout: rule.payout ?? "flat",
      payout_steps: rule.payout === "graded" ? (rule.steps ?? null) : null,
    });
    const browserHash = await sha256Hex(canonicalJson(r.spec));
    await hub("/api/specs", { spec: r.spec });
    const written: Draft = { spec: r.spec, hash: r.hash, browserHash, key: draftKey };
    setDraft(written);
    return written;
  };

  const prepare = () =>
    run("prepare", async () => {
      clearAgreement();
      setNotice(null);
      await writeRule();
    });

  // One-click cases from the top of the page.
  useEffect(() => {
    if (!scenario || !dep) return;
    caseKey.current = scenario.readyMade ? draftKey : null;
    clearAgreement();
    document.getElementById("lock")?.scrollIntoView({ behavior: "smooth" });
    run("prepare", async () => {
      let t = await chainTime();
      // A case replays a past summer. On the local demo chain, roll the clock back
      // instead of stopping at "already started"; a real chain is never rolled back.
      const rolledBack = seasonTiming(year).windowStart <= t && dep.chainId === 31337;
      if (rolledBack) {
        await hub("/api/reset", {});
        t = await chainTime();
      }
      setNow(t);
      if (seasonTiming(year).windowStart <= t) {
        setNotice(`Summer ${year} has already started on this chain, so “${scenario.label}” cannot be locked here.`);
        return;
      }
      setNotice(rolledBack ? `Demo chain rolled back to 1 May 2021 to replay “${scenario.label}”.` : null);
      await writeRule();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario?.nonce, dep]);

  const submitDraft = async (text: Draft) => {
      if (!dep) throw new Error("The local chain is not connected.");
      if (text.key !== draftKey) throw new Error("settings changed; write the rule again");
      if (text.browserHash !== text.hash) throw new Error("browser fingerprint differs; reload before signing");
      const st = text.spec.settlement;
      if (st.contract !== dep.TriggerAgreement.toLowerCase() || st.chain_id !== dep.chainId) throw new Error("rule was written for a different deployment");
      const next = (await publicClient.readContract({ address: dep.TriggerAgreement, abi: dep.abi.TriggerAgreement, functionName: "nextId" })) as bigint;
      const t = st.timing;
      const proposed = await write(dep, "funder", "propose", [
        text.hash,
        st.parties,
        st.token,
        BigInt(st.amount_cents),
        [st.provider_addresses.station, st.provider_addresses.era5],
        [st.normal_keccak.station, st.normal_keccak.era5],
        st.quorum,
        st.on_dispute === "pay" ? 1 : 0,
        { windowStart: t.window_start, windowEnd: t.window_end, reportDeadline: t.report_deadline, disputeWindow: t.dispute_window },
        { seasonDays: (t.window_end - t.window_start) / DAY, maxMissing: text.spec.rule.max_missing_days, maxFilled: text.spec.rule.max_filled_days },
        st.payout_ladder.map(([minDays, bps]: [number, number]) => ({ minDays, bps })),
      ]);
      setId(next);
      const onChain = await readAgreement(dep, next);
      const diff = termMismatches(text.spec, onChain);
      await addLog(
        `Relief fund proposed agreement #${next} with rule ${text.hash.slice(0, 10)}… — ${diff.length ? "TERMS DIFFER: " + diff.join(", ") : "contract terms match the signed text"}`,
        receiptInfo(dep, proposed),
      );
      if (diff.length) throw new Error("Contract terms differ: " + diff.join(", "));
      return next;
  };

  const downloadMemberSheet = (text: any, hash: string) => {
    const url = URL.createObjectURL(new Blob([memberSheet(text, hash, data[text.site.id])], { type: "text/html" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `extremeproof-${text.site.id}-${text.observation_year}-member-summary.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const propose = () => run("propose", async () => { if (draft) await submitDraft(draft); });

  // Convenience for the LOCAL demo only: execute the same three approvals as
  // the individual role cards. The signed spec and contract checks are shared.
  const startDemo = () => run("demo-start", async () => {
    if (!dep || dep.chainId !== 31337) throw new Error("Demo signing is available only on the local development chain.");
    // Replaying a summer the demo clock has passed: roll the local chain back first.
    const rollBack = id === null && seasonTiming(year).windowStart <= await chainTime();
    if (rollBack) {
      await hub("/api/reset", {});
      setNotice(`Demo chain rolled back to 1 May 2021 to replay summer ${year}.`);
    }
    const text = id !== null && draft ? draft : !rollBack && draft?.key === draftKey ? draft : await writeRule();
    if (text.browserHash !== text.hash) throw new Error("browser fingerprint differs; reload before signing");
    if (await chainTime() >= text.spec.settlement.timing.window_start)
      throw new Error("This summer already started on the demo clock. Reset the demo chain, then start again.");
    const agreementId = id ?? await submitDraft(text);
    let current = await readAgreement(dep, agreementId);
    const differences = termMismatches(text.spec, current);
    if (differences.length) throw new Error("Contract terms differ: " + differences.join(", "));
    for (const role of ["funder", "community", "checker"] as const) {
      if (current.approvals & ROLE_BIT[role]) continue;
      const signed = await write(dep, role, "approve", [agreementId, text.hash]);
      await addLog(`${PARTY_INFO[role].name} signed ${text.hash.slice(0, 10)}…${role === "funder" ? " and deposited " + fmtDemo(BigInt(text.spec.settlement.amount_cents)) : ""} (simulated demo role)`, receiptInfo(dep, signed));
      current = await readAgreement(dep, agreementId);
      setAg(current);
    }
    if (current.status !== "Locked") throw new Error("Agreement was not locked. Check the status in step 3.");
    await addLog("All three demo roles signed. The deposit is locked; starting the historical replay.");
    document.getElementById("replay")?.scrollIntoView({ behavior: "smooth" });
    play();
  });

  const approve = (role: string) =>
    run(`approve-${role}`, async () => {
      if (!dep || !draft || id === null) return;
      const signed = await write(dep, role, "approve", [id, draft.hash]);
      await addLog(
        `${PARTY_INFO[role].name} signed ${draft.hash.slice(0, 10)}…${role === "funder" ? " and deposited " + fmtDemo(BigInt(draft.spec.settlement.amount_cents)) : ""}`,
        receiptInfo(dep, signed),
      );
    });

  const resetChain = () =>
    run("reset", async () => {
      await hub("/api/reset", {});
      clearAgreement();
      setNotice("Demo chain rolled back to 1 May 2021. Every summer 2021–2026 can be locked and replayed again.");
    });

  const season = useMemo(() => seasonDates(seasonYear), [seasonYear]);
  const locked = ag && !["Proposed", "Cancelled", "None"].includes(ag.status);
  const lockedBase = spec ? `${spec.rule.base_period[0].slice(0, 4)}-${spec.rule.base_period[1].slice(0, 4)}` : rule.base;
  const lockedPct = spec?.rule.percentile ?? rule.percentile;
  const anomaly = (src: Src) =>
    season.map((iso) => {
      const v = d.series[src][dayIndex(d, iso)];
      const t = d.thresholds[`${src}|${lockedBase}|${lockedPct}`]?.[doy(iso) - 1];
      return v === null || v === undefined || t === null || t === undefined ? null : +(v - t).toFixed(2);
    });
  const stAnom = anomaly("station");
  const erAnom = anomaly("era5");
  const evDays = prov.station.evidence?.season?.days as any[] | undefined;
  const stValues = evDays ? evDays.map((x) => (x.tx === null || x.threshold === null ? null : +(+x.tx - +x.threshold).toFixed(2))) : stAnom;
  const stStyle = evDays ? evDays.map((x) => (x.status === "filled" ? "hollow" : "filled")) : undefined;
  const runLen = (vals: (number | null)[], upto: number) => {
    let best = 0;
    let cur = 0;
    vals.slice(0, upto).forEach((v) => {
      cur = v !== null && v > 0 ? cur + 1 : 0;
      best = Math.max(best, cur);
    });
    return best;
  };
  const missingSoFar = stAnom.slice(0, idx).filter((v) => v === null).length;
  const bands: Band[] = [];
  // Money released during the season, on the day it moved.
  releases.forEach((r) => {
    const i = season.indexOf(r.date);
    if (i >= 0) bands.push({ from: i, to: i, color: "var(--good)", label: `${fmtDemo(r.amount)} released` });
  });
  for (const [src, color] of [["station", "var(--series-1)"], ["era5", "var(--series-2)"]] as const) {
    const sp = prov[src].evidence?.season?.spells as { start: string; end: string; days: number }[] | undefined;
    sp?.filter((s) => s.days >= (spec?.rule.min_spell_days ?? 6)).forEach((s) =>
      bands.push({ from: season.indexOf(s.start), to: season.indexOf(s.end), color, label: `${src} spell ${s.days} days` }),
    );
  }

  const play = () => {
    if (timer.current) clearInterval(timer.current);
    setPlaying(true);
    setIdx(0);
    timer.current = setInterval(() => {
      setIdx((i) => {
        if (i >= season.length) {
          if (timer.current) clearInterval(timer.current);
          setPlaying(false);
          return season.length;
        }
        return i + 2;
      });
    }, 60);
  };
  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    [],
  );
  const seasonOver = idx >= season.length;

  const short = (h: string) => h.slice(0, 10) + "…";
  // During the season: once a week each provider looks at the data already published (5 days behind);
  // if they hold a longer qualifying spell than the chain shows, it posts those days' readings. The
  // contract computes the spell from them; anyone then releases the share both providers' readings support.
  const interimAll = () =>
    run("interim", async () => {
      if (!dep || !draft || id === null || !ag) return;
      let released = BigInt(0);
      for (let ts = ag.timing.windowStart + 7 * DAY; ts < ag.timing.windowEnd; ts += 7 * DAY) {
        await warpTo(ts);
        let any = false;
        for (const p of dep.providers) {
          const r = await call(`${p.url}/report`, { agreement_id: Number(id), spec: draft.spec, interim: true });
          if (!r.reported) continue;
          any = true;
          await addLog(
            `${p.source === "station" ? "Station" : "ERA5"} provider posted ${r.days_posted} days of readings (published to ${r.through}); the contract computed a ${r.longest_spell}-day hot spell against the signed thresholds`,
            await txInfo(dep, r.report_tx),
          );
        }
        if (!any) continue;
        const before = (await readAgreement(dep, id)).paidOut;
        try {
          const rel = await write(dep, "deployer", "release", [id]);
          const after = (await readAgreement(dep, id)).paidOut;
          released += after - before;
          const day = fmtChainDate(await chainTime()).slice(0, 10);
          setReleases((r) => [...r, { date: day, amount: after - before }]);
          await addLog(`Released ${fmtDemo(after - before)} to the cooperative in the middle of the season: the share both providers already support.`, receiptInfo(dep, rel));
        } catch (e) {
          if (revertName(e) !== "NothingToRelease") throw e;
        }
      }
      if (released === BigInt(0)) await addLog("During the season the two records never both showed a qualifying spell, so nothing was released early.");
      setInterimDone(true);
    });

  const reportAll = () =>
    run("report", async () => {
      if (!dep || !draft || id === null || !ag) return;
      await warpTo(ag.timing.windowEnd);
      await addLog("Season over. Chain clock moved to 1 October (simulated clock).");
      const next: Record<Src, ProviderState> = { station: {}, era5: {} };
      for (const p of dep.providers) {
        const name = p.source === "station" ? "Station" : "ERA5";
        try {
          const r = (next[p.source].report = await call(`${p.url}/report`, { agreement_id: Number(id), spec: draft.spec }));
          const ev = (next[p.source].evidence = (await call(`${p.url}/evidence/${id}`)).evidence);
          const fetched = Object.entries(ev.observations as Record<string, { sha256: string }>)
            .map(([k, o]) => `${k === "station" ? "station" : "ERA5"} data ${short(o.sha256)}`)
            .join(" + ");
          const posted = r.days_posted ? `posted the remaining ${r.days_posted} days of readings` : "posted no readings";
          await addLog(
            r.outcome === null
              ? `${name} provider fetched ${fetched} and ${posted}; the contract computed NO VERDICT: ${REASON_TEXT[r.reason] ?? r.reason}`
              : `${name} provider fetched ${fetched} and ${posted}; the contract computed: ${r.outcome ? "heatwave rule MET" : "rule NOT met"}, longest spell ${r.longest_spell} days`,
            r.report_tx ? await txInfo(dep, r.report_tx) : undefined,
          );
        } catch (e: any) {
          next[p.source].error = String(e.message ?? e);
        }
      }
      setProv(next);
    });

  const providerAttack = () =>
    run("attack", async () => {
      if (!dep || id === null) return;
      const p = dep.providers.find((x) => x.source === "era5")!;
      const r = await call(`${p.url}/attack/${id}`, {});
      setAttack((a) => ({ ...a, provider: r }));
      await addLog(`ERA5 provider tried to ${r.attempted} → ${r.accepted ? "ACCEPTED" : "rejected by the contract (" + r.reason + ")"}`);
    });

  const finalize = () =>
    run("finalize", async () => {
      if (!dep || id === null || !draft) return;
      const early = (await readAgreement(dep, id)).paidOut; // released during the season
      const settled = await write(dep, "deployer", "finalize", [id]);
      const a = await readAgreement(dep, id);
      const returned = a.amount - a.paidOut - a.contested;
      await addLog(
        a.status === "Paid"
          ? (early === a.paidOut
            ? `Settled by an outside observer: the final readings confirm the ${fmtDemo(a.paidOut)} already released during the season; nothing more to move${returned ? `, ${fmtDemo(returned)} returned to the fund` : ""}.`
            : `Settled by an outside observer: ${fmtDemo(a.paidOut)} paid to the cooperative's account${early ? ` (${fmtDemo(early)} of it during the season)` : ""}, the share both providers support${returned ? `; ${fmtDemo(returned)} returned to the fund` : ""}.`)
          : a.status === "Refunded"
            ? "Settled: both providers say the rule was not met → deposit returned to the fund."
            : a.contested === a.amount
              ? `Settled: the providers did not agree → all ${fmtDemo(a.amount)} goes to dispute. Nobody can decide alone.`
              : `Settled what the data decide: ${[a.paidOut ? `${fmtDemo(a.paidOut)} paid to the cooperative` : "", returned ? `${fmtDemo(returned)} returned to the fund` : ""].filter(Boolean).join(" and ")} at once; only the providers' difference, ${fmtDemo(a.contested)}, goes to dispute.`,
        receiptInfo(dep, settled),
      );
    });

  const vote = (role: string, pay: boolean) =>
    run(`vote-${role}`, async () => {
      if (!dep || id === null) return;
      const voted = await write(dep, role, "voteDispute", [id, pay]);
      await addLog(`${PARTY_INFO[role].name} voted to ${pay ? "pay" : "refund"}.`, receiptInfo(dep, voted));
    });

  const applyFallback = () =>
    run("fallback", async () => {
      if (!dep || id === null || !ag) return;
      await warpTo(ag.disputeEndsAt);
      const fallback = await write(dep, "deployer", "settleDisputeByDefault", [id]);
      await addLog(`30 days passed without a unanimous decision → the signed fallback applied: ${fmtDemo(ag.contested)} ${ag.onDispute === "pay" ? "paid to the cooperative" : "returned to the fund"} (${ag.onDispute}).`, receiptInfo(dep, fallback));
    });

  const changeRule = () =>
    run("change-rule", async () => {
      if (!dep || id === null || !draft) return;
      const s = draft.spec;
      const other = { ...s, rule: { ...s.rule, base_period: s.rule.base_period[0].startsWith("1961") ? ["1991-01-01", "2020-12-31"] : ["1961-01-01", "1990-12-31"] } };
      const h = await sha256Hex(canonicalJson(other));
      try {
        await write(dep, "funder", "approve", [id, h]);
        setAttack((a) => ({ ...a, changeRule: "ACCEPTED (unexpected)" }));
      } catch (e) {
        setAttack((a) => ({ ...a, changeRule: revertName(e) }));
        await addLog(`Fund tried to sign a different base period after the season → contract refused (${revertName(e)}).`);
      }
      const v = await hub<VerifyResult>(`/api/verify/${id}?tamper_kind=spec_base_period`, {});
      setTamper((t) => ({ ...t, spec_base_period: v }));
    });

  const tamperRun = (kind: string) =>
    run(`tamper-${kind}`, async () => {
      if (id === null) return;
      const v = await hub<VerifyResult>(`/api/verify/${id}?tamper_kind=${kind}`, {});
      setTamper((t) => ({ ...t, [kind]: v }));
    });

  const verify = () =>
    run("verify", async () => {
      if (id === null) return;
      setVerified(await hub<VerifyResult>(`/api/verify/${id}`, {}));
    });

  if (offline)
    return (
      <div className="wrap card">
        <h3>The live part needs the local chain</h3>
        <p className="note">
          Steps 3–6 sign and settle a real agreement on a local blockchain with two provider services. Start them with{" "}
          <code>extremeproof/.venv/Scripts/python -m extremeproof.scripts.stack</code> and reload. ({offline})
        </p>
      </div>
    );
  if (!dep) return <div className="wrap card note">Connecting to the local chain…</div>;

  const reported = Object.values(prov).some((p) => p.report || p.evidence);
  const mismatch = fixed && ag ? termMismatches(spec, ag) : [];
  const liveSettingsDiffer = fixed && draft!.key !== draftKey;
  const goToReplay = () => document.getElementById("replay")?.scrollIntoView({ behavior: "smooth" });
  // One entry point, worded for the step it unlocks, so steps 4-6 never show a dead end.
  // On the local chain startDemo rolls the clock back itself if this summer has passed.
  const demoEntryFor = (title: string, lead: string) => (
    <div className="next-action">
      <strong>{title}</strong>
      <p className="note">{lead}</p>
      <button className="btn" disabled={!!busy} onClick={startDemo}>
        {busy === "demo-start" ? "Signing demo roles…" : `Sign demo agreement & play summer ${seasonYear}`}
      </button>
      {err && <p className="err" role="alert">{err}</p>}
    </div>
  );
  const demoEntry = demoEntryFor("Start with a signed demo agreement",
    "This button proposes the rule, signs as all three simulated parties and locks the DEMO deposit. Then the summer replay starts.");
  const evidenceEntry = (title: string, lead: string) => !locked ? demoEntryFor(title, lead) : (
    <div className="next-action">
      <strong>The providers haven't published their results yet</strong>
      <p className="note">Finish the summer replay, then let the providers report and settle in step 4. That creates the evidence used here.</p>
      <button className="btn" onClick={goToReplay}>Continue replay & publish results →</button>
    </div>
  );

  return (
    <>
      <section className="step" id="lock">
        <div className="wrap">
          <div className="step-head">
            <span className="step-num">3</span>
            <h2>Lock the rule before the season starts</h2>
            <p>
              The rule from step 2 becomes one document. The three parties sign its fingerprint; the fund's signature also deposits the money. After the third
              signature nothing can change — a different rule needs a new agreement — and the contract refuses to lock once the season has begun.
            </p>
          </div>
          <div className="grid-2">
            <div className="card stack" style={{ gap: 12 }}>
              <div className="controls" style={{ marginBottom: 0 }}>
                <label className="field">
                  Season to protect
                  <select value={year} onChange={(e) => setYear(+e.target.value)} disabled={id !== null}>
                    {SEASONS.map((y) => (
                      <option key={y} value={y} disabled={!available.includes(y)}>
                        {y} {available.includes(y) ? "" : "(already started)"}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="field">
                  Demo chain clock
                  <span className="chip">{now ? fmtChainDate(now) : "…"} · simulated</span>
                </div>
              </div>
              {notice && <p className="callout">{notice}</p>}
              {spec ? (
                <SpecSummary spec={spec} data={data} />
              ) : (
                <p className="note">Write the rule to see exactly what the parties will sign: the climate rule from step 2 plus every term the contract will execute.</p>
              )}
              {liveSettingsDiffer && (
                <p className="note">The settings above have changed since signing. They don't affect agreement #{String(id)}; start a new agreement to use them.</p>
              )}
              <div className="btn-row">
                {id === null ? (
                  <>
                    <button className="btn" onClick={prepare} disabled={!!busy || !available.includes(year)}>
                      {draft ? "Rewrite the rule" : "Write the rule"}
                    </button>
                    {draft && (
                      <button className="btn ghost" onClick={propose} disabled={!!busy}>
                        Fund proposes it on chain
                      </button>
                    )}
                  </>
                ) : (
                  <button className="btn ghost" onClick={clearAgreement} disabled={!!busy}>
                    Start a new agreement
                  </button>
                )}
                <button className="btn ghost" onClick={resetChain} disabled={!!busy} title="Roll the local chain back to 1 May 2021">
                  Reset demo chain
                </button>
              </div>
              {draft && (
                <div>
                  <div className="note">Fingerprint (sha256 of the canonical rule)</div>
                  <div className="hash">{draft.hash}</div>
                  <div className="btn-row" style={{ marginTop: 6 }}>
                    {draft.browserHash === draft.hash ? (
                      <span className="chip good">✓ your browser computed the same fingerprint</span>
                    ) : (
                      <span className="chip bad">✕ browser fingerprint differs</span>
                    )}
                    {ag &&
                      (mismatch.length === 0 ? (
                        <span className="chip good">✓ contract terms match the signed text</span>
                      ) : (
                        <span className="chip bad">✕ contract differs: {mismatch.join(", ")}</span>
                      ))}
                  </div>
                  <div className="btn-row" style={{ marginTop: 10 }}>
                    <button className="btn ghost" onClick={() => downloadMemberSheet(draft.spec, draft.hash)}>
                      Download a summary for members (EN/TR)
                    </button>
                    <span className="note">Plain-language page the cooperative can read before its representative signs.</span>
                  </div>
                  <details>
                    <summary className="note" style={{ cursor: "pointer", marginTop: 8 }}>
                      Show the exact text that is signed
                    </summary>
                    <pre className="spec">{JSON.stringify(draft.spec, null, 2)}</pre>
                  </details>
                </div>
              )}
            </div>
            <div className="stack">
              {(["funder", "community", "checker"] as const).map((role) => {
                const done = ag ? (ag.approvals & ROLE_BIT[role]) !== 0 : false;
                return (
                  <div className="card party" key={role}>
                    <div className="who">
                      <div>
                        <strong>{PARTY_INFO[role].name}</strong> <span className="pill sim">simulated</span>
                        <div className="role">{PARTY_INFO[role].role}</div>
                      </div>
                      {done ? <span className="chip good">✓ signed</span> : <span className="chip">waiting</span>}
                    </div>
                    <div className="hash">{dep.roles[role]}</div>
                    <div>
                      <button className="btn ghost" onClick={() => approve(role)} disabled={!!busy || id === null || done || ag?.status !== "Proposed"}>
                        Sign fingerprint{role === "funder" ? " + deposit" : ""}
                      </button>
                    </div>
                  </div>
                );
              })}
              <div className="card">
                <div className="who" style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                  <strong>Agreement {id !== null ? `#${id}` : ""}</strong>
                  <span className={`chip ${ag?.status === "Paid" ? "good" : ag?.status === "Disputed" ? "warn" : ""}`}>{ag?.status ?? "not proposed"}</span>
                </div>
                {bal && (
                  <dl className="kv" style={{ marginTop: 8 }}>
                    <dt>Held by the contract</dt>
                    <dd>{fmtDemo(bal.escrow)}</dd>
                    <dt>Cooperative's account</dt>
                    <dd>{fmtDemo(bal.beneficiary)}</dd>
                  </dl>
                )}
              </div>
            </div>
          </div>
          {err && (
            <p className="err" role="alert">
              Refused: {err}
            </p>
          )}
          <div className="grid-3" style={{ marginTop: 16 }}>
            <div className="fact">
              <strong>No two versions of the rule</strong>
              <p className="small">
                A signature proves who signed a rule, not that they didn't sign a different one for someone else. One public, ordered record of the fingerprint does.
              </p>
            </div>
            <div className="fact">
              <strong>The money is already locked</strong>
              <p className="small">The deposit is escrowed at lock. Once both providers' readings show the heat, the share they support moves; the fund cannot hold it back or reopen the choice of normal.</p>
            </div>
            <div className="fact">
              <strong>Nobody decides alone</strong>
              <p className="small">
                The contract counts the heat from the readings against thresholds signed now; providers only post readings, which anyone can recheck.
                Disagreement needs all three parties or the fallback they signed. If everyone trusts one institution, a database is enough — this is for when they don't.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="step" id="replay">
        <div className="wrap">
          <div className="step-head">
            <span className="step-num">4</span>
            <h2>During and after the season: the contract reads the heat</h2>
            <p>
              The season's data did not exist when the rule was signed. Providers post the daily readings on chain; the contract compares each one
              with the signed threshold for that day and counts the hot spell itself. Days can only be added, never changed, so a spell only grows,
              and the share both providers' readings support is released that week. After the season each posts the rest of the season, naming
              the exact files it used. Observed data only, no forecast.
            </p>
          </div>
          <div className="card stack" style={{ gap: 10 }}>
            {!locked && demoEntry}
            <div className="btn-row">
              {locked && (
              <button className="btn" onClick={play} disabled={!locked || playing || !!busy}>
                {idx ? "Replay again" : `Play summer ${seasonYear}`}
              </button>
              )}
              <span className="note">
                {d.site.name} · day {Math.min(idx, season.length)} of {season.length} · longest hot spell so far: station {runLen(stValues, idx)} days (
                {evDays ? `${evDays.slice(0, idx).filter((x) => x.status === "filled").length} filled by the agreed rule` : `${missingSoFar} missing before gap filling`}
                ), ERA5 {runLen(erAnom, idx)} days
              </span>
            </div>
            <LineChart
              xs={season}
              upto={locked ? Math.max(idx, 1) : season.length}
              zeroLabel={`agreed threshold (${lockedPct}th pct, ${lockedBase.replace("-", "–")})`}
              unit="°C above"
              ariaLabel={`Degrees above each source's own threshold, ${d.site.name}, summer ${seasonYear}`}
              bands={bands}
              series={[
                { id: "st", label: evDays ? "Station (hollow = filled by agreed rule)" : "Station", color: "var(--series-1)", values: stValues, kind: "dots", style: stStyle as any },
                { id: "er", label: "ERA5", color: "var(--series-2)", values: erAnom },
              ]}
              missingRow={{ label: "station day missing", color: "var(--hatch)", missing: stAnom.map((v) => v === null) }}
            />
            {locked && seasonOver && (
              <div className="grid-2">
                <div className="stack" style={{ gap: 10 }}>
                  <div className="btn-row">
                    <button className="btn" onClick={interimAll} disabled={!!busy || interimDone || reported || ag?.status !== "Locked"}>
                      1 · During the season: release as the heat builds
                    </button>
                    <button className="btn" onClick={reportAll} disabled={!!busy || reported}>
                      2 · Providers fetch the season data and report
                    </button>
                    <button className="btn danger" onClick={providerAttack} disabled={!!busy || !prov.era5.report || ag?.status !== "Locked"}>
                      Attack: ERA5 provider lowers the signed hot line by 2 °C
                    </button>
                    <button className="btn" onClick={finalize} disabled={!!busy || !reported || ag?.status !== "Locked"}>
                      3 · Settle (anyone can)
                    </button>
                  </div>
                  {(["station", "era5"] as const).map((src) => {
                    const p = prov[src];
                    return (
                      <div key={src} className="card" style={{ padding: 12 }}>
                        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                          <i className="key-dot" style={{ background: src === "station" ? "var(--series-1)" : "var(--series-2)" }} />
                          <strong>{src === "station" ? "Provider A · station" : "Provider B · ERA5"}</strong>
                          <span className="pill sim">simulated service</span>
                          {p.report?.outcome === null ? (
                            <span className="chip warn">⚠ no verdict</span>
                          ) : p.report ? (
                            <span className={`chip ${p.report.outcome ? "good" : ""}`}>
                              contract: {p.report.outcome ? "rule met" : "rule not met"} · {p.report.longest_spell} days
                            </span>
                          ) : null}
                        </div>
                        {p.report?.outcome === null && (
                          <p className="note">No verdict: {REASON_TEXT[p.report.reason] ?? p.report.reason}. The contract does not count this as “no”.</p>
                        )}
                        {p.evidence?.observations && (
                          <p className="note">
                            Fetched after the season:{" "}
                            {Object.entries(p.evidence.observations as Record<string, { sha256: string }>)
                              .map(([k, o]) => `${k === "station" ? "station" : "ERA5"} ${short(o.sha256)}`)
                              .join(", ")}
                            {p.evidence.season ? `; ${p.evidence.season.filled_days} days filled, ${p.evidence.season.missing_days} missing` : ""}
                            {p.report ? `; readings and evidence ${short(p.report.evidence_digest)} on chain` : ""}
                          </p>
                        )}
                        {p.error && <p className="err">{p.error}</p>}
                      </div>
                    );
                  })}
                  {ag && (["Disputed", "Paid", "Refunded"].includes(ag.status) || ag.paidOut > BigInt(0)) && (() => {
                    const back = ag.amount - ag.paidOut - ag.contested;
                    const parts = [
                      { cls: "paid", label: "paid to the cooperative", v: ag.paidOut },
                      { cls: "held", label: "in dispute", v: ag.contested },
                      { cls: "back", label: "back to the fund", v: back },
                    ].filter((x) => x.v > BigInt(0));
                    return (
                      <div className="deposit card" style={{ padding: 12 }} aria-label="The deposit after settlement, read from the contract">
                        <strong>The {fmtDemo(ag.amount)} deposit, read from the contract{ag.status === "Locked" ? " (season still open)" : ""}</strong>
                        <div className="deposit-bar">
                          {parts.map((x) => <i key={x.cls} className={x.cls} style={{ width: `${(Number(x.v) / Number(ag.amount)) * 100}%` }} />)}
                        </div>
                        <div className="deposit-key">
                          {parts.map((x) => <span key={x.cls}><i className={x.cls} />{fmtDemo(x.v)} {x.label}</span>)}
                        </div>
                      </div>
                    );
                  })()}
                  {attack.provider && (
                    <p className="callout">
                      Attack: {attack.provider.attempted} →{" "}
                      <strong>{attack.provider.accepted ? "accepted" : `rejected by the contract (${attack.provider.reason})`}</strong>.
                    </p>
                  )}
                  {ag?.status === "Disputed" && (
                    <div className="card stack" style={{ gap: 8 }}>
                      <strong>Disputed — the providers did not both agree</strong>
                      <p className="note">
                        {fmtDemo(ag.contested)} is contested{ag.paidOut ? `; ${fmtDemo(ag.paidOut)} was already paid` : ""}. The three parties can settle it only
                        unanimously. Otherwise after 30 days the signed fallback ({ag.onDispute === "pay" ? "pay out" : "refund"}) applies.
                      </p>
                      {(["funder", "community", "checker"] as const).map((role) => (
                        <div className="btn-row" key={role}>
                          <span style={{ minWidth: 170 }}>{PARTY_INFO[role].name}</span>
                          <button className="btn ghost" onClick={() => vote(role, true)} disabled={!!busy}>
                            vote pay
                          </button>
                          <button className="btn ghost" onClick={() => vote(role, false)} disabled={!!busy}>
                            vote refund
                          </button>
                        </div>
                      ))}
                      <div>
                        <button className="btn" onClick={applyFallback} disabled={!!busy}>
                          Skip 30 days → apply the signed fallback
                        </button>
                      </div>
                    </div>
                  )}
                </div>
                <div className="card">
                  <h3>What happened</h3>
                  <Ledger entries={log.map((l) => ({ date: fmtChainDate(l.t).slice(0, 10), text: l.text, tx: l.tx }))} contract={dep.TriggerAgreement} chainId={dep.chainId} />
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="step" id="attack">
        <div className="wrap">
          <div className="step-head">
            <span className="step-num">5</span>
            <h2>Try to cheat</h2>
            <p>Each attack is run for real against the contract or the independent verifier.</p>
          </div>
          {!reported && evidenceEntry("Attacks need a settled agreement",
            "Once a summer is settled you can re-sign the rule with another normal, edit a temperature reading, and flip or drop a provider's evidence. One click signs and replays one.")}
          {reported && (
          <div className="grid-3">
            <div className="card stack" style={{ gap: 8 }}>
              <h3>Change the normal after the heatwave</h3>
              <p className="note">The fund signs a version of the rule with the other base period, which would flip some verdicts.</p>
              <button className="btn danger" onClick={changeRule} disabled={!!busy || !locked}>
                Try it
              </button>
              {attack.changeRule && (
                <p>
                  Contract: <span className="chip bad">refused · {attack.changeRule}</span>
                </p>
              )}
              {tamper.spec_base_period && <Checks res={tamper.spec_base_period} />}
            </div>
            <div className="card stack" style={{ gap: 8 }}>
              <h3>Edit one temperature reading</h3>
              <p className="note">Change a single summer value to 45 °C in the data a party hands over.</p>
              <button className="btn danger" onClick={() => tamperRun("observation")} disabled={!!busy || !reported}>
                Try it
              </button>
              {tamper.observation && <Checks res={tamper.observation} />}
            </div>
            <div className="card stack" style={{ gap: 8 }}>
              <h3>Hide or change a provider's evidence</h3>
              <p className="note">Flip a published verdict, or hand over a bundle without the providers' evidence.</p>
              <div className="btn-row">
                <button className="btn danger" onClick={() => tamperRun("evidence_outcome")} disabled={!!busy || !reported}>
                  Try it
                </button>
                <button className="btn danger" onClick={() => tamperRun("drop_evidence")} disabled={!!busy || !reported}>
                  Drop the evidence
                </button>
              </div>
              {tamper.evidence_outcome && <Checks res={tamper.evidence_outcome} />}
              {tamper.drop_evidence && <Checks res={tamper.drop_evidence} />}
            </div>
          </div>
          )}
        </div>
      </section>

      <section className="step" id="verify">
        <div className="wrap">
          <div className="step-head">
            <span className="step-num">6</span>
            <h2>Check it yourself, without trusting us</h2>
            <p>
              The verifier is one Python file using only the standard library and sharing no code with the providers. It recomputes percentiles, gap filling and
              spells from the raw data, checks that every term the contract executes matches the signed text, accounts for every provider (including justified
              abstentions), and checks the settlement.
            </p>
          </div>
          <div className="grid-2">
            <div className="card stack" style={{ gap: 10 }}>
              <div className="btn-row">
                {reported ? (
                <button className="btn" onClick={verify} disabled={!!busy || !reported}>
                  Run the independent verifier
                </button>
                ) : evidenceEntry("The verifier checks a settled agreement",
                  "It needs the signed rule, both providers' evidence and the settlement on chain. One click signs and replays one.")}
                {id !== null && reported && (
                  <a className="btn ghost" href={`${HUB}/api/bundle/${id}`}>
                    Download verification bundle (.zip)
                  </a>
                )}
              </div>
              {verified && <Checks res={verified} />}
            </div>
            <div className="card">
              <h3>Offline, on your own machine</h3>
              <pre className="spec">{`unzip extremeproof-agreement-${id ?? "N"}.zip
cd extremeproof-agreement-${id ?? "N"}
python verify.py .
python verify.py . --rpc http://127.0.0.1:8545   # also re-read the chain
python verify.py . --refetch                     # compare with the publisher today`}</pre>
              <p className="note" style={{ marginTop: 8 }}>
                The bundle holds the signed rule, the history pinned at signing, the season data each provider fetched, both providers' evidence and a
                snapshot of the chain. <code>--refetch</code> also compares the season data with what the publisher serves today.
              </p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
