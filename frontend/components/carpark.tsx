"use client";

import Link from "next/link";
import {useEffect, useMemo, useRef, useState} from "react";
import {AlertTriangle, Check, Clock3, Download, Fingerprint, Info, Pause, Play, Plug, RefreshCw, ShieldCheck, X, Zap} from "lucide-react";
import {api, download, downloadText, number} from "@/lib/api";
import s from "./carpark.module.css";

type Mode = "priority" | "carbon_flex" | "equal_share";
type Metrics = {sessions: number; served: number; requested_kwh: number; delivered_kwh: number; unserved_kwh: number; max_unserved_kwh: number; emissions_kgco2: number; cost_gbp: number; peak_import_kw: number; peak_envelope_kw: number; cap_exceeded_slots: number; solves: number; solve_seconds: number};
type Car = {id: string; driver: string; arrival_h: number; request_kwh: number; possible_kwh: number; infeasible: boolean; max_kw: number; promise_h: number; departure_quantiles_h: Record<string, number>; history_sessions: number; departure_h: number; effective_departure_h: number; effective_promise_h: number; declared: boolean; delivered_kwh: number; unserved_kwh: number; served: boolean; executed_kwh: number[]};
type Slot = {slot: number; start_utc: string; cap_kw: number; base_kw: number; ev_kw: number; envelope_kw: number; import_kw: number; ci_forecast: number; ci_actual: number; tariff: number; uncontrolled_kw: number; visible: string[]; active: string[]; remaining_kwh: number[]; allocated_kwh: number[]; deadline_slots: number[]; priority: string[]; promise_gap_bound_kwh: number[]};
type CapEvent = {type: "cap"; at_slot: number; from_slot: number; to_slot: number; kw: number};
type LeaveEvent = {type: "leave"; at_slot: number; car_id: string; departure_h: number};
type Event = CapEvent | LeaveEvent;
type Day = {run_id: string; date: string; grid_date: string; mode: Mode; mode_label: string; policy: string; policy_description: string; connection_kw: number; events: Event[]; cars: Car[]; slots: Slot[]; metrics: Metrics; compare: Partial<Record<Mode, Metrics>>; uncontrolled: {peak_envelope_kw: number; slots_over_connection: number}; impossible_requests: number; information_boundary: string; evidence_level: string; model: {selection: {level: number}}};
type Config = {available: boolean; message?: string; days: string[]; day_sessions: Record<string, number>; default_day: string; default_connection_kw: number; source: {doi: string; licence: string; attribution: string}; model: {fit_window: string[]; calibration_window: string[]}};
type Row = {policy_name: string; cap: number; served_pct: number; unserved_pct: number; emissions_kgco2_per_day: number; cost_gbp_per_day: number; peak_import_kw_per_day: number; g_per_delivered_kwh: number; days: number};
type PairedBase = {cap: number; a: string; b: string; metric: string; mean_diff_per_day: number; block_ci95: [number, number]; days_a_better: number; days_a_worse: number};
type FollowRow = Row & {regime: string; served_of_feasible_pct: number; infeasible: number};
type Paired = PairedBase & {regime?: string};
type Followup = {status: string; days: number; sessions: number; impossible_requests: number; capacity_needed_kw: Record<string, Record<string, Record<string, number | null>>>; paired: Paired[]; summary: FollowRow[]};
type Results = {status: string; days: number; sessions: number; coverage: Record<string, {site: Record<string, number>}>; followup: Followup | null};
type Level = {status: string; verified: boolean; errors?: string[]; note?: string; warnings?: string[]};
type Verification = {verified: boolean; status: string; levels: Record<string, Level>; errors: string[]; not_proven: string[]};
type Proof = {evidence_id: string; digest: string; evidence: Record<string, unknown>};
type Forgery = {attack: string; description: string; new_digest: string; rehashed_verification: Verification};

const MODES: [Mode, string][] = [["priority", "GridProof priority"], ["carbon_flex", "Carbon-flex (experimental)"], ["equal_share", "Equal share"]];
// Floor to the minute: a 13:29.99 target belongs to the 13:00 half-hour, so never show it as 13:30.
const clock = (h: number) => {const m = Math.floor(h * 60 + 1e-6); return `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;};
const slotClock = (k: number) => clock(k / 2);
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
const short = (id: string) => id.slice(0, 6);
const LAYERS: [string, string, string][] = [["integrity", "Bytes unchanged", "Canonical SHA-256 equals the digest"], ["physical_service", "Physics & service", "Cap with zero solar, presence, power, energy, arithmetic"], ["decision_replay", "Decision replay", "Policy re-run from decision-time inputs only"], ["source_lineage", "Source correspondence", "Grid from pinned NESO/ERA5; sessions from pinned raw file"]];

export function Carpark() {
  const [config, setConfig] = useState<Config | null>(null);
  const [date, setDate] = useState(""), [kw, setKw] = useState(120), [mode, setMode] = useState<Mode>("priority");
  const [events, setEvents] = useState<Event[]>([]);
  const [day, setDay] = useState<Day | null>(null), [previous, setPrevious] = useState<{metrics: Metrics; label: string} | null>(null);
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  const [tab, setTab] = useState<"replay" | "plan" | "record">("replay");
  const [now, setNow] = useState(48), [playing, setPlaying] = useState(false), [selected, setSelected] = useState<string | null>(null);
  const [results, setResults] = useState<Results | null>(null);
  const pendingLabel = useRef("");
  const request = useRef(0);
  const current = useRef<Day | null>(null);

  useEffect(() => {
    api<Config>("/carpark/config").then(c => {setConfig(c); if (c.available) {setDate(c.default_day); setKw(c.default_connection_kw);}}).catch(e => setError(String(e)));
    api<Results>("/carpark/results").then(setResults).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!date) return;
    const id = ++request.current;
    setBusy("Recomputing every half-hour decision");
    const timer = setTimeout(async () => {
      try {
        const value = await api<Day>("/carpark/day", {date, connection_kw: kw, mode, events});
        if (id !== request.current) return;
        const label = pendingLabel.current; pendingLabel.current = "";
        setPrevious(label && current.current ? {metrics: current.current.metrics, label} : null);
        current.current = value; setDay(value); setError("");
      } catch (e) {if (id === request.current) setError(String(e));}
      finally {if (id === request.current) setBusy("");}
    }, 220);
    return () => clearTimeout(timer);
  }, [date, kw, mode, events]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => setNow(k => {if (k >= 48) {setPlaying(false); return 48;} return k + 1;}), 320);
    return () => clearInterval(timer);
  }, [playing]);

  function change(label: string, apply: () => void) {pendingLabel.current = label; apply();}
  function play() {
    if (!day) return;
    if (playing) {setPlaying(false); return;}
    if (now >= 48) setNow(Math.max(0, Math.floor(Math.min(...day.cars.map(c => c.arrival_h)) * 2)));
    setPlaying(true);
  }

  if (config && !config.available) return <div className={s.app}><Header /><main className={s.main}><div className={s.error} role="alert"><b>Real session data is not on this machine.</b><p>{config.message}</p><code className={s.code}>.venv/Scripts/python.exe scripts/fetch_workplace_sessions.py</code></div></main></div>;

  const compareKey: Mode = mode === "equal_share" ? "priority" : "equal_share";
  const other = day?.compare[compareKey];
  const otherLabel = compareKey === "equal_share" ? "equal share" : "GridProof priority";

  return <div className={s.app}>
    <Header />
    <main className={s.main}>
      <section className={s.intro}>
        <div>
          <div className={s.eyebrow}>Staff car park · shared connection · {day ? `${day.cars.length} drivers on ${day.date}` : "loading"}</div>
          <h1>More drivers leave with the charge they asked for, on the connection you already have.</h1>
          <p>GridProof learns when each driver usually leaves and charges the likely early leavers first, without ever exceeding the site&apos;s connection limit. Replay a real held-out day, change the conditions and check the record.</p>
        </div>
      </section>

      <section className={s.controls} aria-label="Replay settings">
        <label className={s.field}>Real day (held out, 2024)
          <select value={date} onChange={e => {setEvents([]); setPrevious(null); setNow(48); setDate(e.target.value);}} aria-label="Replay day">
            {config?.days.map(d => <option key={d} value={d}>{d} · {config.day_sessions[d]} drivers</option>)}
          </select>
        </label>
        <div className={`${s.field} ${s.rangeField}`}>
          <label htmlFor="connection">Connection limit</label>
          <div className={s.rangeRow}><input id="connection" type="range" min={80} max={200} step={10} value={kw} onChange={e => change(`connection ${kw} → ${e.target.value} kW`, () => setKw(+e.target.value))} /><span className={`${s.rangeValue} ${s.mono}`}>{kw} kW</span></div>
        </div>
        <div className={s.field}>Charging strategy
          <div className={s.segmented} role="group" aria-label="Charging strategy">
            {MODES.map(([key, label]) => <button key={key} aria-pressed={mode === key} onClick={() => change(`strategy → ${label}`, () => setMode(key))}>{label}</button>)}
          </div>
        </div>
        <div className={s.computeState} role="status">{busy ? <><RefreshCw size={13} className={s.spin} />{busy}</> : day ? <><Check size={13} />Recomputed live · {day.metrics.solves ? `${day.metrics.solves} optimisations` : "48 half-hour decisions"}</> : null}</div>
      </section>

      {error && <div className={s.error} role="alert"><b>Could not compute this replay.</b> {error} <span className={s.hint}>Check that the API is running, then change a setting to retry. The previous result stays on screen.</span></div>}

      {day && <section className={`${s.tiles} ${busy ? s.stale : ""}`} aria-label="Outcome of this replay">
        <Tile label="Requests met in full" icon={<Check size={14} />} value={<>{day.metrics.served}<small>of {day.metrics.sessions}</small></>}
          note={<>{other && <Delta value={day.metrics.served - other.served} unit="" goodWhenPositive text={`${otherLabel}: ${other.served}`} />}{day.impossible_requests > 0 && <><br />{day.impossible_requests} could not be met at 11 kW before the driver left, by any schedule (hindsight)</>}</>} />
        <Tile label="Energy short at departure" icon={<AlertTriangle size={14} />} value={<>{number(day.metrics.unserved_kwh, 1)}<small>kWh</small></>}
          note={other && <Delta value={day.metrics.unserved_kwh - other.unserved_kwh} unit=" kWh" goodWhenPositive={false} text={`${otherLabel}: ${number(other.unserved_kwh, 1)} kWh`} />} />
        <Tile label="Connection limit" icon={<Plug size={14} />} value={day.metrics.cap_exceeded_slots === 0 ? <>Never exceeded</> : <span className={s.worse}>{day.metrics.cap_exceeded_slots} half-hours over</span>}
          note={<>Uncontrolled charging would peak at <b>{number(day.uncontrolled.peak_envelope_kw, 0)} kW</b>{day.uncontrolled.slots_over_connection ? `, over the limit for ${day.uncontrolled.slots_over_connection} half-hours` : ""}</>} />
        <Tile label="Grid carbon (modelled)" icon={<Zap size={14} />} value={<>{number(day.metrics.emissions_kgco2, 0)}<small>kg CO₂</small></>}
          note={other && <>{otherLabel}: {number(other.emissions_kgco2, 0)} kg; delivers {number(day.metrics.delivered_kwh - other.delivered_kwh, 1)} kWh {day.metrics.delivered_kwh >= other.delivered_kwh ? "more" : "less"}</>} />
      </section>}
      {previous && day && <p className={s.effect} role="status"><b>Effect of {previous.label}:</b> requests met {previous.metrics.served} → {day.metrics.served}; short {number(previous.metrics.unserved_kwh, 1)} → {number(day.metrics.unserved_kwh, 1)} kWh; carbon {number(previous.metrics.emissions_kgco2, 0)} → {number(day.metrics.emissions_kgco2, 0)} kg.</p>}

      <nav className={s.tabs} role="tablist" aria-label="Views">
        {([["replay", "Replay the day"], ["plan", `Across ${results?.days ?? 185} held-out days`], ["record", "Record & verify"]] as const).map(([key, label]) =>
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => setTab(key)}>{label}</button>)}
      </nav>

      {tab === "replay" && day && <Replay day={day} now={now} setNow={k => {setPlaying(false); setNow(k);}} playing={playing} play={play} busy={!!busy}
        selected={selected} setSelected={setSelected}
        addEvent={(e, label) => change(label, () => setEvents(list => [...list, e]))}
        removeEvent={i => change("removing a change", () => setEvents(list => list.filter((_, j) => j !== i)))} events={events} />}
      {tab === "plan" && <Planning results={results} kw={kw} />}
      {tab === "record" && day && <Record day={day} stale={!!busy} />}

      <footer className={s.footer}>
        <span>Driver sessions: {config?.source.attribution}, doi:{config?.source.doi} ({config?.source.licence}). Grid: NESO carbon intensity and ERA5 radiation, 2025.</span>
        <span>A request is the energy each real session took; the data has no battery state of charge. Historical replay with simulated chargers. Modelled location-based emissions, not measured abatement. No hardware commands.</span>
      </footer>
    </main>
  </div>;
}

function Header() {
  return <header className={s.header}>
    <Link href="/" className={s.brand}><span className={s.brandMark}><Zap size={15} /></span>GridProof <span className={s.brandSub}>Workplace charging</span></Link>
    <div className={s.headerLinks}><span className={s.modeChip}><span className={s.dot} />Historical replay · decisions recomputed</span></div>
  </header>;
}

function Tile({label, icon, value, note}: {label: string; icon: React.ReactNode; value: React.ReactNode; note: React.ReactNode}) {
  return <div className={s.tile}><div className={s.tileLabel}>{icon}{label}</div><div className={s.tileValue}>{value}</div><div className={s.tileNote}>{note}</div></div>;
}

function Delta({value, unit, goodWhenPositive, text}: {value: number; unit: string; goodWhenPositive: boolean; text: string}) {
  const zero = Math.abs(value) < 0.05;
  const good = zero ? null : (value > 0) === goodWhenPositive;
  return <>{text}{!zero && <> · <span className={good ? s.better : s.worse}>{value > 0 ? "+" : "−"}{number(Math.abs(value), unit ? 1 : 0)}{unit}</span></>}</>;
}

function Replay({day, now, setNow, playing, play, busy, selected, setSelected, addEvent, removeEvent, events}: {day: Day; now: number; setNow: (k: number) => void; playing: boolean; play: () => void; busy: boolean; selected: string | null; setSelected: (id: string | null) => void; addEvent: (e: Event, label: string) => void; removeEvent: (i: number) => void; events: Event[]}) {
  const tNow = now / 2, end = now >= 48;
  const t0 = Math.max(0, Math.floor(Math.min(...day.cars.map(c => c.arrival_h))) - 1);
  const t1 = Math.min(24, Math.ceil(Math.max(...day.cars.map(c => c.effective_departure_h))) + 1);
  const x = (h: number) => `${((h - t0) / (t1 - t0)) * 100}%`;
  const visible = day.cars.filter(c => c.arrival_h <= tNow + 1e-9).sort((a, b) => a.arrival_h - b.arrival_h);
  const slot = day.slots[Math.min(now, 47)];
  const byId = Object.fromEntries(day.cars.map(c => [c.id, c]));
  const delivered = (c: Car) => sum(c.executed_kwh.slice(0, now));
  const connected = visible.filter(c => c.effective_departure_h > tNow);
  const charging = end ? [] : slot.active.filter((_, i) => slot.allocated_kwh[i] > 1e-6);
  const ticks = Array.from({length: t1 - t0 + 1}, (_, i) => t0 + i).filter(h => h % 2 === 0);
  const car = selected ? byId[selected] : null;
  return <div className={`${s.replayGrid} ${busy ? s.stale : ""}`}>
    <section className={s.panel} aria-label="Day replay">
      <div className={s.scrubber}>
        <button className={s.play} onClick={play} aria-label={playing ? "Pause replay" : "Replay the day"}>{playing ? <Pause size={14} /> : <Play size={14} />}{playing ? "Pause" : "Replay"}</button>
        <span className={`${s.clock} ${s.mono}`}>{end ? "24:00" : slotClock(now)}</span>
        <input type="range" min={0} max={48} value={now} onChange={e => setNow(+e.target.value)} aria-label="Replay time (UTC)" />
      </div>
      <div className={s.viewNote}>{end ? <><Info size={14} />End of day: hindsight view with every arrival and departure revealed.</> : <><Clock3 size={14} />Controller&apos;s view at {slotClock(now)} UTC: future arrivals and departures are hidden, exactly as they were for every decision.</>}</div>
      <LoadChart day={day} now={now} t0={t0} t1={t1} x={x} ticks={ticks} />
      <div className={s.legend} aria-hidden="true">
        <span><i className={s.keyRect} style={{background: "var(--ev)"}} />EV charging</span>
        <span><i className={s.keyRect} style={{background: "var(--base)"}} />Building load</span>
        <span><i className={s.keyDash} style={{borderColor: "var(--ink)"}} />Connection limit</span>
        <span><i className={s.keyLine} style={{borderColor: "var(--uncontrolled)"}} />Uncontrolled charging</span>
        <span><i className={s.keyDiamond} />Ready-by target</span>
      </div>
      <div className={s.lanes} role="table" aria-label="Drivers">
        <div className={s.laneHead} role="row"><span role="columnheader">Driver · request</span><span role="columnheader">Plugged in · charging per half-hour (UTC)</span><span role="columnheader">Status at {end ? "departure" : slotClock(now)}</span></div>
        {visible.length === 0 && <p className={s.hint} style={{padding: "10px 0"}}>No car has arrived yet at {slotClock(now)}.</p>}
        {visible.map(c => {
          const left = c.effective_departure_h <= tNow + 1e-9;
          const got = end ? c.delivered_kwh : delivered(c);
          const promise = c.declared ? c.effective_promise_h : c.promise_h;
          const idx = slot.active.indexOf(c.id);
          const status = left ? (c.served ? <span className={`${s.status} ${s.sGood}`}><Check size={13} />Request met</span> : <span className={`${s.status} ${s.sBad}`}><AlertTriangle size={13} /><span>{number(c.unserved_kwh, 1)} kWh short{c.infeasible && <span className={s.statusText}>, impossible</span>}</span></span>)
            : got >= c.request_kwh - 0.05 ? <span className={`${s.status} ${s.sGood}`}><Check size={13} /><span>Met<span className={s.statusText}>, still parked</span></span></span>
              : idx >= 0 && slot.allocated_kwh[idx] > 1e-6 ? <span className={`${s.status} ${s.sWarn}`}><Zap size={13} /><span>{number(got, 0)}/{number(c.request_kwh, 0)}<span className={s.statusText}> kWh</span></span></span>
                : <span className={`${s.status} ${s.sIdle}`}><Clock3 size={13} /><span><span className={s.statusText}>Waiting </span>{number(got, 0)}/{number(c.request_kwh, 0)}</span></span>;
          const until = left ? c.effective_departure_h : tNow;
          return <div className={s.lane} role="row" key={c.id} data-selected={selected === c.id} tabIndex={0} aria-label={`${c.driver}: details`}
            onClick={() => setSelected(selected === c.id ? null : c.id)} onKeyDown={e => {if (e.key === "Enter" || e.key === " ") {e.preventDefault(); setSelected(selected === c.id ? null : c.id);}}}>
            <span className={s.laneName} role="cell"><b className={s.mono}>{c.driver === "shared" ? "shared" : c.driver}</b><small>{number(c.request_kwh, 0)} kWh</small></span>
            <span className={s.track} role="cell" aria-label={`Arrived ${clock(c.arrival_h)}, ${left ? `left ${clock(c.effective_departure_h)}` : "still connected"}, ready-by target ${clock(promise)}`}>
              <span className={`${s.plug} ${left ? "" : s.plugOpen}`} style={{left: x(c.arrival_h), width: `calc(${x(until)} - ${x(c.arrival_h)})`}} />
              {c.executed_kwh.slice(0, now).map((e, k) => e > 1e-6 && <span key={k} className={s.cell} style={{left: `calc(${x(k / 2)} + 1px)`, width: `calc(${x(k / 2 + .5)} - ${x(k / 2)} - 2px)`, height: `${Math.max(2, Math.min(1, e / (c.max_kw / 2)) * 14)}px`}} />)}
              <span className={s.promise} style={{left: x(promise)}} title={`Ready-by target ${clock(promise)}`} />
              {left && <span className={`${s.depart} ${c.served ? "" : s.departShort}`} style={{left: x(c.effective_departure_h)}} />}
              {!end && <span className={s.nowLine} style={{left: x(tNow)}} />}
            </span>
            <span role="cell">{status}</span>
          </div>;
        })}
        <div className={s.axisRow} aria-hidden="true"><span /><span className={`${s.axisTicks} ${s.mono}`}>{ticks.map(h => <span key={h} data-minor={h % 4 ? "" : undefined} style={{left: x(h)}}>{String(h).padStart(2, "0")}:00</span>)}</span><span /></div>
      </div>
    </section>

    <aside className={s.rail}>
      {car && <section className={s.panel} aria-label="Selected driver">
        <div className={s.panelHead}><div><h2 className={s.mono}>{car.driver}</h2><p>{car.history_sessions} earlier sessions in the training history</p></div><button className={s.secondary} onClick={() => setSelected(null)} aria-label="Close driver details"><X size={14} /></button></div>
        <div className={s.panelBody}>
          <table className={s.table}><tbody>
            <tr><td>Plugged in</td><td className={s.mono}>{clock(car.arrival_h)}</td></tr>
            <tr><td>Requested</td><td>{number(car.request_kwh, 1)} kWh at up to {number(car.max_kw, 0)} kW{car.infeasible && car.effective_departure_h <= tNow + 1e-9 ? ` · at most ${number(car.possible_kwh, 1)} kWh was possible before this departure (known only afterwards)` : ""}</td></tr>
            <tr><td>Ready-by target</td><td className={s.mono}>{clock(car.promise_h)}{car.declared ? ` → declared ${clock(car.effective_promise_h)}` : ""}</td></tr>
            <tr><td>Predicted unplug</td><td className={s.mono}>1 in 10 by {clock(car.departure_quantiles_h["0.10"])} · half by {clock(car.departure_quantiles_h["0.50"])}</td></tr>
            <tr><td>Actually left</td><td className={s.mono}>{car.effective_departure_h <= tNow + 1e-9 ? clock(car.effective_departure_h) : "not yet known"}</td></tr>
            <tr><td>Delivered</td><td>{number(car.effective_departure_h <= tNow + 1e-9 ? car.delivered_kwh : delivered(car), 1)} kWh</td></tr>
          </tbody></table>
          <p className={s.hint} style={{marginTop: 8}}>The target is the time by which 80% of similar plug-ins are still connected, from this driver&apos;s earlier sessions. It sets charging order, not a guarantee.</p>
        </div>
      </section>}

      <section className={s.panel} aria-label="Controller state">
        <div className={s.panelHead}><div><h2>{end ? "How the day ended" : `At ${slotClock(now)} UTC`}</h2><p>{day.mode_label}: {day.policy_description}</p></div></div>
        <div className={s.panelBody}>
          {end ? <>
            <div className={s.stateList}><div><b>{day.metrics.served}</b><span>left with their full request</span></div><div><b>{day.metrics.sessions - day.metrics.served}</b><span>left short</span></div></div>
            {day.cars.filter(c => !c.served).length > 0 ? <ul className={s.queue}>{day.cars.filter(c => !c.served).sort((a, b) => b.unserved_kwh - a.unserved_kwh).slice(0, 6).map(c => <li key={c.id}><AlertTriangle size={14} color="var(--bad)" /><span className={s.mono}>{c.driver} left {clock(c.effective_departure_h)}</span><b>−{number(c.unserved_kwh, 1)} kWh</b></li>)}</ul>
              : <p className={s.hint} style={{marginTop: 8}}>Nobody left short today.</p>}
            <p className={s.hint} style={{marginTop: 10}}>Press Replay or drag the time to see what the controller knew at each decision.</p>
          </> : <>
            <div className={s.stateList}><div><b>{connected.length}</b><span>plugged in</span></div><div><b>{charging.length}</b><span>charging now</span></div><div><b>{connected.filter(c => delivered(c) >= c.request_kwh - .05).length}</b><span>already full</span></div><div><b>{number(slot.cap_kw - slot.base_kw, 0)}</b><span>kW available for cars</span></div></div>
            {day.policy === "equal_share" ? <p className={s.hint} style={{marginTop: 10}}>Equal share splits the available power evenly among {slot.active.length} cars still charging. It has no idea who leaves first.</p>
              : day.policy === "optimised" ? <p className={s.hint} style={{marginTop: 10}}>Carbon-flex (experimental) re-optimises the rest of the day for carbon, cost and departure risk; charging now: {charging.length} cars. On realistic inputs it met fewer requests than equal share, so it is not recommended.</p>
                : <><p className={s.hint} style={{marginTop: 10}}>Charging order now (earliest ready-by target first):</p>
                  <ol className={s.queue}>{slot.priority.slice(0, 6).map((id, i) => <li key={id}><span className={s.rank}>{i + 1}</span><span className={s.mono}>{byId[id]?.driver} · by {clock(byId[id]?.declared && byId[id]?.effective_promise_h ? byId[id].effective_promise_h : byId[id]?.promise_h)}</span><span>{number(slot.allocated_kwh[slot.active.indexOf(id)] * 2, 0)} kW</span></li>)}</ol></>}
            {day.policy !== "uncontrolled" && <div className={s.bound}>{sum(slot.promise_gap_bound_kwh) > 0.05
              ? <><AlertTriangle size={13} color="var(--bad)" /> <b>At least {number(sum(slot.promise_gap_bound_kwh), 1)} kWh</b> cannot reach these cars by their ready-by targets, whatever the schedule. Arrivals after now can only add to this.</>
              : <><Check size={13} color="var(--good)" /> Every plugged-in car can still be full by its ready-by target (exact bound over all schedules for the cars connected now).</>}</div>}
          </>}
        </div>
      </section>

      <Interventions day={day} now={now} connected={connected} addEvent={addEvent} removeEvent={removeEvent} events={events} jump={setNow} />
    </aside>
  </div>;
}

function LoadChart({day, now, t0, t1, x, ticks}: {day: Day; now: number; t0: number; t1: number; x: (h: number) => string; ticks: number[]}) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const H = 150, W = 1000;
  const shown = day.slots.filter(sl => sl.slot / 2 >= t0 && sl.slot / 2 < t1);
  const knownCap = (k: number) => {
    let cap = day.connection_kw;
    for (const e of day.events) if (e.type === "cap" && e.at_slot <= Math.min(now, 47) && e.from_slot <= k && k < e.to_slot) cap = e.kw;
    return now >= 48 ? day.slots[k].cap_kw : cap;
  };
  const top = Math.max(...day.slots.map(sl => Math.max(sl.cap_kw, sl.uncontrolled_kw, sl.envelope_kw))) * 1.08;
  const X = (h: number) => ((h - t0) / (t1 - t0)) * W, Y = (v: number) => H - (v / top) * H;
  const past = shown.filter(sl => sl.slot < now);
  const area = (f: (sl: Slot) => number, g: (sl: Slot) => number) => past.length ? past.map(sl => `M${X(sl.slot / 2)},${Y(g(sl))}H${X(sl.slot / 2 + .5)}V${Y(f(sl))}H${X(sl.slot / 2)}Z`).join("") : "";
  const step = (vals: [number, number][]) => vals.map(([h, v], i) => `${i ? "L" : "M"}${X(h)},${Y(v)}L${X(h + .5)},${Y(v)}`).join("");
  const yTicks = [0, 50, 100, 150, 200, 250].filter(v => v < top);
  function move(e: React.PointerEvent) {
    const box = ref.current!.getBoundingClientRect();
    const h = t0 + ((e.clientX - box.left) / box.width) * (t1 - t0);
    const k = Math.floor(h * 2);
    setHover(k >= 0 && k < 48 && k < now ? k : null);
  }
  const hv = hover !== null ? day.slots[hover] : null;
  return <div className={s.lanes} style={{paddingBottom: 0}}>
    <div className={`${s.lane} ${s.chartGrid}`} style={{borderBottom: 0, alignItems: "stretch"}}>
      <span style={{position: "relative", fontSize: 11, color: "var(--muted)"}}>
        <b className={s.loadTitle} style={{fontSize: 12, color: "var(--ink-2)"}}>Site load, kW</b>
        {yTicks.map(v => <span key={v} className={s.mono} style={{position: "absolute", right: 0, top: `${18 + Y(v) - 8}px`}}>{v}</span>)}
      </span>
      <div ref={ref} style={{position: "relative", marginTop: 18}} onPointerMove={move} onPointerLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{width: "100%", height: H, display: "block"}} role="img" aria-label={`Site load against the ${day.connection_kw} kW connection limit`}>
          {yTicks.map(v => <line key={v} x1={0} x2={W} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" strokeWidth={1} vectorEffect="non-scaling-stroke" />)}
          <path d={area(sl => sl.base_kw, () => 0)} fill="var(--base)" />
          <path d={area(sl => sl.envelope_kw, sl => sl.base_kw)} fill="var(--ev)" opacity={.85} />
          <path d={step(past.map(sl => [sl.slot / 2, sl.uncontrolled_kw]))} fill="none" stroke="var(--uncontrolled)" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          <path d={step(shown.map(sl => [sl.slot / 2, knownCap(sl.slot)]))} fill="none" stroke="var(--ink)" strokeWidth={1.5} strokeDasharray="5 4" vectorEffect="non-scaling-stroke" />
          {hv && <line x1={X(hv.slot / 2 + .25)} x2={X(hv.slot / 2 + .25)} y1={0} y2={H} stroke="var(--ink-2)" strokeWidth={1} vectorEffect="non-scaling-stroke" />}
        </svg>
        {now < 48 && <span className={s.nowLine} style={{left: x(now / 2), top: 0, bottom: 0}} />}
        {hv && <div className={s.tooltip} style={{left: `min(calc(${x(hv.slot / 2)} + 12px), calc(100% - 180px))`, top: 4}}>
          <b className={s.mono}>{slotClock(hv.slot)}–{slotClock(hv.slot + 1)} UTC</b>
          <div className={s.tipRow}><span><i className={s.keyLine} style={{borderColor: "var(--ev)"}} />EV charging</span><b>{number(hv.ev_kw, 0)} kW</b></div>
          <div className={s.tipRow}><span><i className={s.keyLine} style={{borderColor: "var(--base)"}} />Building</span><b>{number(hv.base_kw, 0)} kW</b></div>
          <div className={s.tipRow}><span><i className={s.keyLine} style={{borderColor: "var(--ink)"}} />Limit</span><b>{number(hv.cap_kw, 0)} kW</b></div>
          <div className={s.tipRow}><span><i className={s.keyLine} style={{borderColor: "var(--uncontrolled)"}} />Uncontrolled</span><b>{number(hv.uncontrolled_kw, 0)} kW</b></div>
          <div className={s.tipRow}><span>Grid carbon (actual)</span><b>{number(hv.ci_actual, 0)} g/kWh</b></div>
        </div>}
      </div>
      <span className={s.loadSide} style={{fontSize: 11, color: "var(--muted)", paddingTop: 18}}>Peak {number(day.metrics.peak_envelope_kw, 0)} kW<br />limit {day.connection_kw} kW</span>
    </div>
    <div className={s.srOnly}><table><caption>Half-hourly site load</caption><thead><tr><th>Time</th><th>EV kW</th><th>Building kW</th><th>Limit kW</th></tr></thead><tbody>{past.map(sl => <tr key={sl.slot}><td>{slotClock(sl.slot)}</td><td>{number(sl.ev_kw, 1)}</td><td>{number(sl.base_kw, 1)}</td><td>{number(sl.cap_kw, 0)}</td></tr>)}</tbody></table></div>
  </div>;
}

function Interventions({day, now, connected, addEvent, removeEvent, events, jump}: {day: Day; now: number; connected: Car[]; addEvent: (e: Event, label: string) => void; removeEvent: (i: number) => void; events: Event[]; jump: (k: number) => void}) {
  const at = Math.min(now, 47);
  const [capKw, setCapKw] = useState(70), [from, setFrom] = useState(at), [to, setTo] = useState(at + 4);
  const [carId, setCarId] = useState(""), [leaveAt, setLeaveAt] = useState(at + 2);
  useEffect(() => {setFrom(at); setTo(Math.min(48, at + 4)); setLeaveAt(Math.min(48, at + 2));}, [at]);
  const options = (min: number, max = 48) => Array.from({length: max - min + 1}, (_, i) => min + i).map(k => <option key={k} value={k}>{slotClock(k)}</option>);
  const car = connected.find(c => c.id === carId) ?? connected[0];
  const disabled = now >= 48;
  return <section className={s.panel} aria-label="Respond to a change">
    <div className={s.panelHead}><div><h2>Something changed at {disabled ? "…" : slotClock(at)}</h2><p>{disabled ? "Drag the replay time to the moment the change is announced." : "Applied from this moment. Energy already delivered is never rewritten."}</p></div></div>
    <div className={s.panelBody}>
      {disabled ? <div className={s.jump}><p className={s.hint}>Changes are announced during the day, so the controller only learns about them from that moment.</p><button className={s.secondary} onClick={() => jump(19)}><Clock3 size={14} />Go to 09:30, the busiest hour</button></div> : <>
      <div className={s.form}>
        <b style={{fontSize: 13}}>The grid operator asks you to limit imports</b>
        <div className={s.formRow}>
          <label className={s.field}>Limit kW<input type="number" min={20} max={400} value={capKw} onChange={e => setCapKw(+e.target.value)} /></label>
          <label className={s.field}>From<select value={from} onChange={e => setFrom(+e.target.value)}>{options(at, 47)}</select></label>
          <label className={s.field}>Until<select value={to} onChange={e => setTo(+e.target.value)}>{options(Math.max(from + 1, at + 1))}</select></label>
        </div>
        <button className={s.secondary} disabled={disabled || to <= from} onClick={() => addEvent({type: "cap", at_slot: at, from_slot: from, to_slot: to, kw: capKw}, `a ${capKw} kW limit ${slotClock(from)}–${slotClock(to)}`)}>Apply grid request</button>
      </div>
      <hr className={s.divider} />
      <div className={s.form}>
        <b style={{fontSize: 13}}>A driver says they must leave early</b>
        <div className={s.formRow} style={{gridTemplateColumns: "2fr 1fr"}}>
          <label className={s.field}>Driver<select value={car?.id ?? ""} onChange={e => setCarId(e.target.value)} disabled={!connected.length}>{connected.map(c => <option key={c.id} value={c.id}>{c.driver} · {number(c.request_kwh, 0)} kWh</option>)}</select></label>
          <label className={s.field}>Leaves at<select value={leaveAt} onChange={e => setLeaveAt(+e.target.value)}>{options(at + 1)}</select></label>
        </div>
        <button className={s.secondary} disabled={disabled || !car} onClick={() => car && addEvent({type: "leave", at_slot: at, car_id: car.id, departure_h: leaveAt / 2}, `${car.driver} leaving at ${slotClock(leaveAt)}`)}>Tell the controller</button>
        <p className={s.hint}>What-if: the driver really leaves then. Their time becomes a firm deadline in GridProof's queue; equal share has no queue. Cars already past their target still come first.</p>
      </div></>}
      {events.length > 0 && <><hr className={s.divider} /><div className={s.events} aria-label="Applied changes">{events.map((e, i) => <span className={s.eventChip} key={i}>
        {e.type === "cap" ? `${slotClock(e.at_slot)}: limit ${e.kw} kW ${slotClock(e.from_slot)}–${slotClock(e.to_slot)}` : `${slotClock(e.at_slot)}: ${day.cars.find(c => c.id === e.car_id)?.driver} leaves ${clock(e.departure_h)}`}
        <button onClick={() => removeEvent(i)} aria-label="Remove this change"><X size={12} /></button></span>)}</div></>}
    </div>
  </section>;
}

function Planning({results, kw}: {results: Results | null; kw: number}) {
  const [table, setTable] = useState(false), [hover, setHover] = useState<number | null>(null);
  const [regime, setRegime] = useState<"decision_time" | "original">("decision_time");
  if (!results) return <p className={s.hint}>Loading the held-out evaluation…</p>;
  if (results.status !== "ready" || !results.followup) return <div className={s.error}>Held-out results are not available. Run scripts/evaluate_carpark.py --stage test and scripts/evaluate_carpark_followup.py.</div>;
  const f = results.followup;
  const series: [string, string, string, string][] = [
    // Validated reference slot order (blue, orange, aqua, yellow); identity also carried by legend, direct labels and table.
    ["edf_lightgbm_original_choice", "var(--ev)", "solid", "GridProof (LightGBM)"], ["equal_share", "var(--uncontrolled)", "solid", "Equal share"],
    ["edf_population", "var(--aqua)", "solid", "Arrival time only"], ["edf_personal_quantile", "var(--yellow)", "solid", "Simple personal history"],
    ["edf_oracle_departures", "var(--oracle)", "dash", "Known departures"]];
  const rows = f.summary.filter(r => r.regime === regime);
  const caps = Array.from(new Set(rows.map(r => r.cap))).filter(c => rows.filter(r => r.cap === c).length > 3).sort((a, b) => a - b);
  const get = (p: string, cap: number, reg: string = regime) => f.summary.find(r => r.regime === reg && r.policy_name === p && r.cap === cap);
  const threshold = regime === "decision_time" ? ">=90%" : ">=95%";
  const need = (p: string) => f.capacity_needed_kw[regime]?.[p]?.[threshold];
  const pair = (cap: number, a: string, b: string, m = "served", reg: string = regime) => f.paired.find(r => r.regime === reg && r.cap === cap && r.a === a && r.b === b && r.metric === m);
  const ceiling = regime === "decision_time" ? 100 * (1 - f.impossible_requests / f.sessions) : 100;
  const W = 640, H = 300, L = 44, B = 30, R = 165, lo = 50;
  const X = (c: number) => L + ((c - caps[0]) / (caps[caps.length - 1] - caps[0])) * (W - L - R), Y = (v: number) => (H - B) - ((v - lo) / (100 - lo)) * (H - B - 10);
  const ends = series.map(([p]) => [p, Y(get(p, caps[caps.length - 1])?.served_pct ?? lo)] as const).sort((a, b) => a[1] - b[1]);
  const labelY: Record<string, number> = {};
  ends.forEach(([p, y], i) => {labelY[p] = i ? Math.max(y, labelY[ends[i - 1][0]] + 15) : y;});
  const gp = "edf_lightgbm_original_choice";
  const vsSimple = pair(120, gp, "edf_personal_quantile", "served", "decision_time"), vsSimple100 = pair(100, gp, "edf_personal_quantile", "served", "decision_time");
  const simpleVsPop = pair(120, "edf_personal_quantile", "edf_population", "served", "decision_time");
  const flexServed = pair(150, "carbon_flex", "equal_share", "served", "decision_time"), flexCo2 = pair(150, "carbon_flex", "equal_share", "emissions_kgco2", "decision_time");
  const pre = pair(120, gp, "equal_share", "served", "original"), dt = pair(120, gp, "equal_share", "served", "decision_time");
  const ci = (p?: Paired) => p ? `${number(p.block_ci95[0], 2)} to ${number(p.block_ci95[1], 2)}` : "";
  return <div className={s.planGrid}>
    <section className={s.panel}>
      <div className={s.panelHead}><div><div className={s.eyebrow}>{f.days} held-out weekdays · {f.sessions.toLocaleString("en-GB")} real sessions · {regime === "decision_time" ? "post-review check, exploratory" : "pre-registered, tested once"}</div>
        <p className={s.headline}>To meet {threshold.slice(2)} of requests in full, GridProof needs a {need(gp)} kW connection. Equal share needs {need("equal_share") ?? "more than 200"} kW.</p>
        <p>{regime === "decision_time"
          ? <>Every car limited to 11 kW, requests declared at plug-in and never capped. {number(100 - ceiling, 1)}% of requests could not be met before the driver left by any schedule (dotted ceiling). Same days, same drivers.</>
          : <>As pre-registered: each request capped, and power set, using the real departure. That made every request servable, so these numbers overstate what a deployed controller can know.</>} Tested in 10 kW steps on one site&apos;s replayed sessions: a planning signal, not a connection design value.</p>
        <div className={s.segmented} role="group" aria-label="Input assumptions" style={{marginTop: 8}}>
          <button aria-pressed={regime === "decision_time"} onClick={() => setRegime("decision_time")}>Decision-time inputs</button>
          <button aria-pressed={regime === "original"} onClick={() => setRegime("original")}>Pre-registered inputs</button>
        </div></div></div>
      <div className={s.legend}>{series.map(([p, c, d, label]) => <span key={p}><i className={d === "dash" ? s.keyDash : s.keyLine} style={{borderColor: c}} />{label}</span>)}</div>
      {!table ? <div className={s.chartWrap} onPointerLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Share of requests met in full by connection size"
          onPointerMove={e => {const box = (e.currentTarget as SVGSVGElement).getBoundingClientRect(); const cx = ((e.clientX - box.left) / box.width) * W; setHover(caps.reduce((a, b) => Math.abs(X(b) - cx) < Math.abs(X(a) - cx) ? b : a));}}>
          {[50, 60, 70, 80, 90, 100].map(v => <g key={v}><line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="var(--grid)" /><text x={L - 8} y={Y(v) + 4} textAnchor="end" fontSize={11} fill="var(--muted)">{v}%</text></g>)}
          {caps.filter(c => c % 20 === 0).map(c => <text key={c} x={X(c)} y={H - 8} textAnchor="middle" fontSize={11} fill="var(--muted)">{c} kW</text>)}
          {ceiling < 100 && <g><line x1={L} x2={W - R} y1={Y(ceiling)} y2={Y(ceiling)} stroke="var(--ink-2)" strokeDasharray="1 3" /><text x={L + 4} y={Y(ceiling) - 5} fontSize={10} fill="var(--ink-2)">physical ceiling at 11 kW, {number(ceiling, 1)}%</text></g>}
          <line x1={X(kw)} x2={X(kw)} y1={10} y2={H - B} stroke="var(--ink)" strokeDasharray="3 3" /><text x={X(kw) + 4} y={H - B - 6} fontSize={11} fill="var(--ink-2)">your setting</text>
          {series.map(([p, c, d, label]) => {const pts = caps.map(cap => [cap, get(p, cap)?.served_pct ?? NaN] as const).filter(([, v]) => Number.isFinite(v)); const last = pts[pts.length - 1];
            return <g key={p}><path d={pts.map(([cap, v], i) => `${i ? "L" : "M"}${X(cap)},${Y(Math.max(lo, v))}`).join("")} fill="none" stroke={c} strokeWidth={2} strokeDasharray={d === "dash" ? "5 4" : undefined} />
              {pts.map(([cap, v]) => <circle key={cap} cx={X(cap)} cy={Y(Math.max(lo, v))} r={hover === cap ? 4.5 : 2.5} fill={c} stroke="var(--surface)" strokeWidth={2} />)}
              <line x1={X(last[0]) + 3} x2={X(last[0]) + 12} y1={Y(last[1])} y2={labelY[p]} stroke={c} strokeWidth={1} />
              <text x={X(last[0]) + 15} y={labelY[p] + 4} fontSize={11} fill="var(--ink-2)">{label} {number(last[1], 1)}%</text></g>;})}
          {hover !== null && <line x1={X(hover)} x2={X(hover)} y1={10} y2={H - B} stroke="var(--ink-2)" strokeWidth={1} />}
        </svg>
        {hover !== null && <div className={s.tooltip} style={{left: `${(X(hover) / W) * 100}%`, top: 40, transform: hover > 160 ? "translateX(-110%)" : "translateX(12px)"}}>
          <b>{hover} kW connection</b>
          {series.map(([p, c, , label]) => <div key={p} className={s.tipRow}><span><i className={s.keyLine} style={{borderColor: c}} />{label}</span><b>{number(get(p, hover)?.served_pct, 1)}%</b></div>)}
        </div>}
      </div> : <div className={s.panelBody}><div className={s.tableWrap}><table className={s.table}><thead><tr><th>Connection</th>{series.map(([p, , , label]) => <th key={p}>{label}</th>)}</tr></thead><tbody>{caps.map(c => <tr key={c}><td>{c} kW</td>{series.map(([p]) => <td key={p}>{number(get(p, c)?.served_pct, 1)}% · {number(get(p, c)?.unserved_pct, 2)}% kWh short</td>)}</tr>)}</tbody></table></div></div>}
      <div className={s.panelBody} style={{paddingTop: 0}}><button className={s.textButton} onClick={() => setTable(!table)}>{table ? "Show chart" : "Show as table"}</button></div>
    </section>
    <div className={s.findings}>
      <div className={s.finding}><h3>Same connection, more requests met</h3><p>At 120 kW on decision-time inputs, GridProof meets {number(get(gp, 120, "decision_time")?.served_pct, 1)}% of requests in full versus {number(get("equal_share", 120, "decision_time")?.served_pct, 1)}% for equal share{dt && <>: +{number(dt.mean_diff_per_day, 2)} drivers a day (95% CI {ci(dt)}), better on {dt.days_a_better} days, worse on {dt.days_a_worse}</>}. That is about half the pre-registered gain{pre && <> (+{number(pre.mean_diff_per_day, 2)})</>}, which relied on inputs capped with hindsight. Neither ever exceeds the limit.</p></div>
      <div className={s.finding}><h3>The value is personal history, not LightGBM</h3><p>A simple quantile of each driver&apos;s own past stays gets almost all of it. LightGBM minus simple personal history{vsSimple && <> is {number(vsSimple.mean_diff_per_day, 2)} drivers a day at 120 kW (CI {ci(vsSimple)})</>}{vsSimple100 && <> and {number(vsSimple100.mean_diff_per_day, 2)} at 100 kW (CI {ci(vsSimple100)})</>}. Arrival time alone is clearly worse{simpleVsPop && <> (simple personal history +{number(simpleVsPop.mean_diff_per_day, 2)} a day, CI {ci(simpleVsPop)})</>}. LightGBM stays because validation picked it, not because it is proven better.</p></div>
      <div className={s.finding}><h3>Carbon-flex is not recommended</h3><p>On decision-time inputs at 150 kW it lowers modelled emissions{flexCo2 && <> ({number(flexCo2.mean_diff_per_day, 2)} kg a day, CI {ci(flexCo2)})</>} but meets fewer requests than equal share{flexServed && <> ({number(flexServed.mean_diff_per_day, 2)} drivers a day, CI {ci(flexServed)})</>}. Priority charging raises total emissions because it delivers more energy. Departure risk limits load shifting at a workplace.</p></div>
      <div className={s.finding}><h3>Calibration held on the unseen year</h3><p>{number(100 * (results.coverage.lightgbm?.site["0.10"] ?? 0), 1)}% of drivers left before their predicted “1 in 10” time and {number(100 * (results.coverage.lightgbm?.site["0.20"] ?? 0), 1)}% before the “1 in 5” target (nominal 10% and 20%). Model fitted on 2021–22, calibrated on 2023 H1, choices fixed on 2023 H2.</p></div>
      <div className={s.finding}><h3>What this evidence is</h3><p>Real Dutch office car-park sessions replayed on same-weekday GB grid days, with a synthetic building load and simulated chargers. One site. A “request” is the energy that real session took (no battery state of charge is available). The decision-time view was added after two external reviews and after 2024 had been examined, so it is exploratory, not new independent validation.</p></div>
    </div>
  </div>;
}

function Record({day, stale}: {day: Day; stale: boolean}) {
  const [proof, setProof] = useState<Proof | null>(null), [check, setCheck] = useState<Verification | null>(null);
  const [forgeries, setForgeries] = useState<Record<string, Forgery>>({});
  const [receipt, setReceipt] = useState<{status: string; claim_key?: string; transaction_hash?: string; error?: {code: string; message: string}; readback?: {status: string}} | null>(null);
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  useEffect(() => {setProof(null); setCheck(null); setForgeries({}); setReceipt(null);}, [day.run_id]);
  async function build() {
    setBusy("Building and verifying the record"); setError("");
    try {const p = await api<Proof>("/carpark/evidence", {run_id: day.run_id}); setProof(p); setCheck(await api<Verification>("/carpark/verify", {evidence: p.evidence, expected_digest: p.digest}));}
    catch (e) {setError(String(e));} finally {setBusy("");}
  }
  async function forge(attack: string) {
    if (!proof) return; setBusy("Forging and re-checking");
    try {const f = await api<Forgery>("/carpark/forge", {evidence_id: proof.evidence_id, attack}); setForgeries(v => ({...v, [attack]: f}));}
    catch (e) {setError(String(e));} finally {setBusy("");}
  }
  async function attest() {
    if (!proof) return; setBusy("Registering on the local development chain");
    try {setReceipt(await api("/carpark/attest", {evidence_id: proof.evidence_id}));} catch (e) {setError(String(e));} finally {setBusy("");}
  }
  function csv() {
    const ids = day.cars.map(c => c.id);
    const rows = day.slots.map(sl => [sl.start_utc, sl.cap_kw, sl.base_kw, sl.ev_kw, sl.import_kw, sl.ci_actual, ...ids.map(id => day.cars.find(c => c.id === id)!.executed_kwh[sl.slot])].join(","));
    downloadText(`${day.run_id}.csv`, [["start_utc", "limit_kw", "building_kw", "ev_kw", "import_kw", "grid_gco2_per_kwh", ...day.cars.map(c => `${c.driver}_${c.id}_kwh`)].join(","), ...rows].join("\n"), "text/csv");
  }
  const enabled = !stale && !busy;
  return <div className={stale ? s.stale : ""}>
    <section className={s.panel}>
      <div className={s.panelHead}><div><h2>One checkable record of this day&apos;s control</h2><p>For the sustainability reviewer, a driver disputing a missed charge, or the grid operator that asked for a limit. It separates what the controller knew, what it did and what happened.</p></div><Fingerprint size={22} /></div>
      <div className={s.panelBody}>
        <div className={s.actions}>
          <button className={s.primary} disabled={!enabled} onClick={build}><ShieldCheck size={15} />{proof ? "Rebuild & verify" : "Build & verify this record"}</button>
          <button className={s.secondary} disabled={!enabled} onClick={csv}><Download size={14} />Half-hourly CSV</button>
          {proof && <button className={s.secondary} onClick={() => download(`${proof.evidence_id}.json`, proof)}><Download size={14} />Record JSON</button>}
          {busy && <span className={s.hint}><RefreshCw size={12} className={s.spin} /> {busy}</span>}
        </div>
        <p className={s.hint} style={{marginTop: 8}}>Run <span className={s.mono}>{day.run_id}</span>. The record, CSV and screens all come from this one computation; changing a setting makes a new run.</p>
        {error && <div className={s.error} role="alert">{error}</div>}
        {check && proof && <>
          <Layers result={check} />
          <p className={s.code}>SHA-256 {proof.digest}</p>
          <hr className={s.divider} />
          <h3 style={{margin: "0 0 4px", fontSize: 15}}>Could someone dress up a bad day?</h3>
          <p className={s.hint} style={{marginBottom: 10}}>Every forgery is re-hashed, so “bytes unchanged” passes. The other layers must catch them.</p>
          <div className={s.attacks}>
            {([["hide_shortfall", "Hide a missed charge", "Add the missing energy to one driver's recorded charging and mark them full."], ["move_departure", "Pretend a driver stayed longer", "Move a departure 2 hours later and recompute every number consistently."], ["drop_sessions", "Leave out the drivers who were short", "Report a smaller day without them and recompute every number consistently."]] as const).map(([key, title, text]) => <div className={s.attack} key={key}>
              <h3>{title}</h3><p>{text}</p>
              <button className={s.secondary} disabled={!enabled} onClick={() => forge(key)}>Forge + re-hash</button>
              {forgeries[key] && <div role="status" style={{marginTop: 10}}><b className={forgeries[key].rehashed_verification.verified ? s.worse : s.better}>{forgeries[key].rehashed_verification.verified ? "Forgery accepted (unexpected)" : "Forgery rejected"}</b><Layers result={forgeries[key].rehashed_verification} compact /><p className={s.hint}>{forgeries[key].rehashed_verification.errors.slice(0, 2).join(" · ")}</p></div>}
            </div>)}
          </div>
          <hr className={s.divider} />
          <details>
            <summary style={{cursor: "pointer", fontWeight: 600}}>Optional: commit this record to a shared registry (local development chain)</summary>
            <p className={s.hint} style={{margin: "8px 0"}}>A signed database is enough inside one organisation. A shared registry helps when the site and a counterparty, such as the grid operator settling a flexibility request, should both see one append-only commitment per site-day that neither can quietly replace. This local chain only demonstrates that protocol.</p>
            <button className={s.secondary} disabled={!enabled || !check.verified} onClick={attest}>Register this record locally</button>
            {receipt && <p className={s.hint} style={{marginTop: 8}}>Status: <b>{receipt.status}</b>{receipt.readback ? ` · read back: ${receipt.readback.status}` : ""}{receipt.error ? ` · ${receipt.error.code}: ${receipt.error.message}` : ""}</p>}
            {receipt?.error?.code === "DUPLICATE_ACTIVE_CLAIM" && <p className={s.hint}>A record for this site-day is already registered. Another setting is a different record; the registry keeps one active commitment per site-day.</p>}
            {receipt?.transaction_hash && <p className={s.code}>tx {receipt.transaction_hash}</p>}
          </details>
          <p className={s.hint} style={{marginTop: 12}}><b>Not proven by any layer:</b> {check.not_proven.join("; ")}.</p>
        </>}
      </div>
    </section>
  </div>;
}

function Layers({result, compact}: {result: Verification; compact?: boolean}) {
  return <div className={s.layers} style={compact ? {gridTemplateColumns: "1fr 1fr", margin: "8px 0"} : undefined}>
    {LAYERS.map(([key, label, note]) => {const level = result.levels[key]; const ok = level?.verified; const neutral = level?.status === "CONSTRAINTS_ONLY" || level?.status === "INCOMPLETE";
      return <div className={s.layer} key={key}><span>{label}</span><b className={ok ? s.sGood : neutral ? s.sWarn : s.sBad}>{ok ? <Check size={14} /> : neutral ? <Info size={14} /> : <AlertTriangle size={14} />}{level?.status ?? "—"}</b>{!compact && <small>{level?.status === "CONSTRAINTS_ONLY" ? "Optimiser decisions: constraint-checked, not re-solved" : note}</small>}</div>;})}
  </div>;
}
