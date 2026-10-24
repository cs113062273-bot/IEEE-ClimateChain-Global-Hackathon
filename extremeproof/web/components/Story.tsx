"use client";
import { useMemo, useState } from "react";
import { LineChart, YearBars } from "./charts";
import { SitePicker } from "./SitePicker";
import { dayIndex, doy, seasonDates, verdict, type SiteData } from "@/lib/rule";

const RECENT = [2021, 2022, 2023, 2024, 2025, 2026];
const MIN_SPELL = 6; // the default rule's minimum hot spell

export function Story({ data, site, setSite }: { data: Record<string, SiteData>; site: string; setSite: (s: string) => void }) {
  const d = data[site];
  const [source, setSource] = useState<"station" | "era5">("era5");
  const [year, setYear] = useState(2024);
  const days = seasonDates(year);
  const tx = days.map((iso) => d.series[source][dayIndex(d, iso)] ?? null);
  const th = (base: string) => days.map((iso) => d.thresholds[`${source}|${base}|90`][doy(iso) - 1]);
  const t61 = th("1961-1990");
  const t91 = th("1991-2020");
  const missing = days.map((iso) => d.series.station[dayIndex(d, iso)] === null);
  const nMissing = missing.filter(Boolean).length;

  const facts = useMemo(() => {
    const season = seasonDates(2001).map(doy);
    const diffs = season.map((k) => (d.thresholds["era5|1991-2020|90"][k - 1] ?? 0) - (d.thresholds["era5|1961-1990|90"][k - 1] ?? 0));
    const mean = diffs.reduce((a, b) => a + b, 0) / diffs.length;
    const warmer = diffs.filter((x) => x > 0).length;
    const rule = { variant: "era5" as const, percentile: 90 as const, minSpell: MIN_SPELL, maxMissing: 0, maxFilled: 0, onDispute: "refund" as const };
    const flips = d.years
      .filter((y) => y <= 2025)
      .filter((y) => verdict(d, { ...rule, base: "1961-1990" }, y).state !== verdict(d, { ...rule, base: "1991-2020" }, y).state);
    // Sixty summers against one fixed line: the longest run above the 1961–1990 hot line (ERA5).
    // Years inside the base period use the median bootstrap replicate, as the engine does.
    const years = d.years.filter((y) => y <= 2025);
    const spells = years.map((y) => {
      const v = verdict(d, { ...rule, base: "1961-1990" }, y);
      return v.state === "nodata" ? null : Math.round(v.payoutSpell ?? v.longest ?? 0);
    });
    const count = (a: number, b: number) => years.filter((y, i) => y >= a && y <= b && (spells[i] ?? 0) >= rule.minSpell).length;
    return { mean, warmer, total: diffs.length, flips, years, spells, early: count(1966, 1995), late: count(1996, 2025) };
  }, [d]);

  return (
    <div className="stack">
      <div className="controls">
        <div className="field">
          Place
          <SitePicker site={site} setSite={setSite} label="Place" />
        </div>
        <div className="field">
          Data
          <div className="seg" role="group" aria-label="Data source">
            <button aria-pressed={source === "era5"} onClick={() => setSource("era5")}>
              ERA5 reanalysis
            </button>
            <button aria-pressed={source === "station"} onClick={() => setSource("station")}>
              Weather station
            </button>
          </div>
        </div>
        <label className="field">
          Summer
          <select value={year} onChange={(e) => setYear(+e.target.value)}>
            {RECENT.map((y) => (
              <option key={y}>{y}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid-story">
        <div className="card">
          <h3>
            {d.site.name}, summer {year}: daily maximum temperature against two definitions of “unusually hot”
          </h3>
          <p className="note" style={{ marginBottom: 6 }}>
            “Unusually hot” here is the 90th percentile for that calendar day, computed over a 30-year base period (ETCCDI definition).
          </p>
          <LineChart
            xs={days}
            ariaLabel={`Daily maximum temperature in ${d.site.name}, June to September ${year}, with the 90th percentile thresholds of 1961–1990 and 1991–2020`}
            series={[
              { id: "t61", label: "Hot threshold, 1961–1990", color: "var(--series-3)", values: t61 },
              { id: "t91", label: "Hot threshold, 1991–2020", color: "var(--series-4)", values: t91 },
              source === "era5"
                ? { id: "tx", label: `ERA5 daily max ${year}`, color: "var(--series-2)", values: tx }
                : { id: "tx", label: `Station daily max ${year}`, color: "var(--series-1)", values: tx, kind: "dots" },
            ]}
            missingRow={source === "station" ? { label: "station day missing", color: "var(--hatch)", missing } : undefined}
          />
        </div>
        <div className="stack">
          <div className="fact">
            <div className="big">
              {facts.mean >= 0 ? "+" : ""}
              {facts.mean.toFixed(1)} °C
            </div>
            <div className="small">
              Average change of the summer “unusually hot” line from 1961–1990 to 1991–2020 (ERA5). Higher on {facts.warmer} of {facts.total} days, lower on the
              rest — the normal moved, and not uniformly.
            </div>
          </div>
          <div className="fact">
            <div className="big">{facts.flips.length} summers</div>
            <div className="small">
              where the same heat rule (6+ days above the line, ERA5) gives a different verdict depending only on which 30 years count as normal:{" "}
              {facts.flips.join(", ")}.
            </div>
          </div>
          <div className="fact">
            <div className="big">
              {nMissing} of {days.length}
            </div>
            <div className="small">
              summer days in {year} with no reading from the {d.site.name} weather station ({d.station.id}). Who decides what goes in those gaps?
            </div>
          </div>
        </div>
      </div>
      <div className="card">
        <h3>
          Sixty summers in {d.site.name}: the longest run of unusually hot days, against one fixed line
        </h3>
        <p className="note" style={{ marginBottom: 6 }}>
          ERA5, days above the 1961–1990 calendar-day 90th percentile. A run of {MIN_SPELL} or more days happened in <strong>{facts.early} of 30 summers in
          1966–1995</strong> and <strong>{facts.late} of 30 in 1996–2025</strong>. A relief rule calibrated on the past pays more often as the climate
          warms, so the normal, the line and the expected frequency are signed together.
        </p>
        <YearBars
          years={facts.years}
          values={facts.spells}
          line={MIN_SPELL}
          lineLabel={`${MIN_SPELL}+ days in a row`}
          unit="days"
          ariaLabel={`Longest run of days above the 1961–1990 90th percentile in ${d.site.name}, each summer 1966–2025, ERA5`}
          halves={[{ from: 1966, to: 1995, label: "1966–95" }, { from: 1996, to: 2025, label: "1996–2025" }]}
        />
      </div>
      <p className="callout">
        Climate is the long-run statistics of weather in a place. ExtremeProof computes exactly that — this place's own 30-year normal and its hottest days —
        so that money promised for a heatwave goes out when the heat really was unusual for <em>this</em> place, under a rule nobody can change afterwards.
      </p>
    </div>
  );
}
