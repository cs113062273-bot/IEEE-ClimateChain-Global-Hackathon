"use client";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fmtDay } from "@/lib/rule";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(640);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(260, Math.round(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

function niceTicks(lo: number, hi: number, n = 5) {
  const span = hi - lo || 1;
  const step0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= n) ?? 10 * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

export interface LineSeries {
  id: string;
  label: string;
  color: string; // CSS var, e.g. "var(--series-1)"
  values: (number | null)[];
  kind?: "line" | "dots";
  /** per-point marker style for dots: "filled" observed, "hollow" estimated */
  style?: ("filled" | "hollow")[];
}

export interface Band {
  from: number;
  to: number;
  color: string;
  label: string;
}

export function LineChart({
  xs,
  series,
  unit = "°C",
  height = 300,
  zeroLabel,
  bands = [],
  upto,
  ariaLabel,
  tableTitle,
  missingRow,
}: {
  xs: string[];
  series: LineSeries[];
  unit?: string;
  height?: number;
  zeroLabel?: string;
  bands?: Band[];
  upto?: number; // draw only indices < upto (replay)
  ariaLabel: string;
  tableTitle?: string;
  missingRow?: { label: string; color: string; missing: boolean[] };
}) {
  const [ref, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const n = xs.length;
  const limit = upto ?? n;
  const m = { l: 40, r: 14, t: 12, b: missingRow ? 44 : 28 };
  const H = height;
  const iw = W - m.l - m.r;
  const ih = H - m.t - m.b;
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null && Number.isFinite(v)));
  if (zeroLabel) all.push(0);
  const lo = Math.floor(Math.min(...all) - 0.5);
  const hi = Math.ceil(Math.max(...all) + 0.5);
  const yt = niceTicks(lo, hi, 5);
  const y0 = Math.min(lo, yt[0]);
  const y1 = Math.max(hi, yt[yt.length - 1]);
  const x = (i: number) => m.l + (n <= 1 ? 0 : (i / (n - 1)) * iw);
  const y = (v: number) => m.t + ih - ((v - y0) / (y1 - y0)) * ih;
  const months = xs.map((d, i) => [d, i] as const).filter(([d]) => d.slice(8) === "01");

  const paths = useMemo(
    () =>
      series.map((s) => {
        if (s.kind === "dots") return "";
        let p = "";
        let pen = false;
        s.values.forEach((v, i) => {
          if (i >= limit || v === null) {
            pen = false;
            return;
          }
          p += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
          pen = true;
        });
        return p;
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [series, limit, W, y0, y1, n],
  );

  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const r = (e.currentTarget as SVGRectElement).getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * iw;
    setHover(Math.max(0, Math.min(limit - 1, Math.round((px / iw) * (n - 1)))));
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") setHover((h) => Math.min(limit - 1, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? limit) - 1));
    else if (e.key === "Escape") setHover(null);
  };
  const hv = hover !== null && hover < limit ? hover : null;
  const ttLeft = hv === null ? 0 : x(hv) > W * 0.6 ? x(hv) - 190 : x(hv) + 12;

  return (
    <div>
      <div className="legend" aria-hidden>
        {series.map((s) => (
          <span key={s.id}>
            {s.kind === "dots" ? <i className="key-dot" style={{ background: s.color }} /> : <i className="key-line" style={{ background: s.color }} />}
            {s.label}
          </span>
        ))}
        {missingRow && (
          <span>
            <i className="key-line" style={{ background: missingRow.color, height: 6 }} />
            {missingRow.label}
          </span>
        )}
        {zeroLabel && (
          <span>
            <i className="key-line" style={{ background: "var(--ink-2)" }} />
            {zeroLabel}
          </span>
        )}
        {bands.length > 0 && (
          <span>
            <i className="key-line" style={{ background: "var(--axis)", height: 8, opacity: 0.6 }} />
            shaded: qualifying hot spell (provider colour)
          </span>
        )}
      </div>
      <div className="chart-wrap" ref={ref}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={ariaLabel}
          tabIndex={0}
          onKeyDown={onKey}
          onBlur={() => setHover(null)}
        >
          {bands.map((b, i) => (
            <g key={i}>
              <rect x={x(b.from) - 2} y={m.t} width={Math.max(4, x(b.to) - x(b.from) + 4)} height={ih} fill={b.color} opacity={0.12} rx={3} />
            </g>
          ))}
          {yt.map((v) => (
            <g key={v}>
              <line x1={m.l} x2={W - m.r} y1={y(v)} y2={y(v)} stroke="var(--grid)" strokeWidth={1} />
              <text x={m.l - 6} y={y(v) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {v}
              </text>
            </g>
          ))}
          <text x={4} y={m.t + 2} fontSize={11} fill="var(--muted)" dominantBaseline="hanging">
            {unit}
          </text>
          {zeroLabel && (
            <line x1={m.l} x2={W - m.r} y1={y(0)} y2={y(0)} stroke="var(--ink-2)" strokeWidth={1.25} />
          )}
          <line x1={m.l} x2={W - m.r} y1={m.t + ih} y2={m.t + ih} stroke="var(--axis)" strokeWidth={1} />
          {months.map(([d, i]) => (
            <text key={d} x={x(i)} y={m.t + ih + 16} fontSize={11} fill="var(--muted)" textAnchor={i === 0 ? "start" : "middle"}>
              {fmtDay(d)}
            </text>
          ))}
          {missingRow && (
            <g>
              {missingRow.missing.map((miss, i) =>
                miss && i < limit ? (
                  <rect key={i} x={x(i) - Math.max(1, iw / n / 2)} y={H - 14} width={Math.max(2, iw / n)} height={6} fill={missingRow.color} />
                ) : null,
              )}
            </g>
          )}
          {series.map((s, si) =>
            s.kind === "dots" ? (
              <g key={s.id}>
                {s.values.map((v, i) =>
                  v === null || i >= limit ? null : s.style?.[i] === "hollow" ? (
                    <circle key={i} cx={x(i)} cy={y(v)} r={3.5} fill="var(--surface)" stroke={s.color} strokeWidth={1.5} />
                  ) : (
                    <circle key={i} cx={x(i)} cy={y(v)} r={3.5} fill={s.color} stroke="var(--surface)" strokeWidth={1.5} />
                  ),
                )}
              </g>
            ) : (
              <path key={s.id} d={paths[si]} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            ),
          )}
          {hv !== null && <line x1={x(hv)} x2={x(hv)} y1={m.t} y2={m.t + ih} stroke="var(--ink-2)" strokeWidth={1} />}
          {hv !== null &&
            series.map((s) => {
              const v = s.values[hv];
              return v === null ? null : <circle key={s.id} cx={x(hv)} cy={y(v)} r={4.5} fill={s.color} stroke="var(--surface)" strokeWidth={2} />;
            })}
          <rect
            x={m.l}
            y={m.t}
            width={iw}
            height={ih}
            fill="transparent"
            onPointerMove={onMove}
            onPointerDown={onMove}
            onPointerLeave={() => setHover(null)}
          />
        </svg>
        {hv !== null && (
          <div className="tooltip" style={{ left: ttLeft, top: 8 }} role="status">
            <div className="tt-title">{fmtDay(xs[hv])} {xs[hv].slice(0, 4)}</div>
            {series.map((s) => (
              <div className="tt-row" key={s.id}>
                <span className="tt-key">
                  <i className="key-line" style={{ background: s.color }} />
                  {s.label}
                </span>
                <b>
                  {s.values[hv] === null ? "no data" : `${(s.values[hv] as number).toFixed(1)} ${unit}`}
                  {s.style?.[hv] === "hollow" ? " (filled)" : ""}
                </b>
              </div>
            ))}
            {missingRow?.missing[hv] && <div className="note">{missingRow.label}</div>}
          </div>
        )}
      </div>
      <button className="table-toggle" onClick={() => setTable((t) => !t)} aria-expanded={table}>
        {table ? "Hide table" : "Show as table"}
      </button>
      {table && (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="sr-only">{tableTitle ?? ariaLabel}</caption>
            <thead>
              <tr>
                <th>Date</th>
                {series.map((s) => (
                  <th key={s.id}>{s.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xs.slice(0, limit).map((d, i) => (
                <tr key={d}>
                  <td>{d}</td>
                  {series.map((s) => (
                    <td key={s.id}>
                      {s.values[i] === null ? "–" : (s.values[i] as number).toFixed(1)}
                      {s.style?.[i] === "hollow" ? "*" : ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export type CellState = "met" | "not" | "nodata" | "dispute";
const STATE_TEXT: Record<CellState, string> = { met: "met / pays", not: "not met / refunds", nodata: "no verdict", dispute: "dispute" };
export interface MatrixRow {
  id: string;
  label: string;
  selected?: boolean;
  cells: { state: CellState; detail: ReactNode }[];
}

export function Matrix({
  years,
  rows,
  ariaLabel,
  onPick,
  flags,
  flagLabel,
}: {
  years: number[];
  rows: MatrixRow[];
  ariaLabel: string;
  onPick?: (id: string) => void;
  flags: boolean[];
  flagLabel: string;
}) {
  const [hover, setHover] = useState<{ r: number; c: number } | null>(null);
  const [table, setTable] = useState(false);
  const cell = 13;
  const gap = 2;
  const labelW = 156;
  const top = 22;
  const W = labelW + years.length * (cell + gap) + 4;
  const H = top + rows.length * (cell + 8 + gap) + 4;
  const disagree = flags;
  return (
    <div>
      <div className="legend" aria-hidden>
        <span>
          <i className="key-dot" style={{ background: "var(--ink)" }} /> rule met · agreement pays
        </span>
        <span>
          <i className="key-dot" style={{ border: "1.5px solid var(--axis)", background: "transparent" }} /> not met · agreement refunds
        </span>
        <span>
          <i className="key-dot" style={{ background: "repeating-linear-gradient(45deg, var(--hatch) 0 2px, transparent 2px 4px)" }} /> no verdict (too little data)
        </span>
        <span>
          <i className="key-dot" style={{ background: "var(--warning)", borderRadius: 2, transform: "rotate(45deg)" }} /> agreement goes to dispute
        </span>
        <span>
          <i className="key-line" style={{ background: "var(--warning)", width: 10, height: 4 }} /> {flagLabel}
        </span>
      </div>
      <div className="matrix-scroll chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: W, maxWidth: "none" }} role="img" aria-label={ariaLabel}>
          <defs>
            <pattern id="hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="4" height="4" fill="var(--surface)" />
              <line x1="0" y1="0" x2="0" y2="4" stroke="var(--hatch)" strokeWidth="2" />
            </pattern>
          </defs>
          {years.map((yr, c) =>
            yr % 5 === 0 ? (
              <text key={yr} x={labelW + c * (cell + gap) + cell / 2} y={10} fontSize={10.5} textAnchor="middle" fill="var(--muted)">
                {yr}
              </text>
            ) : null,
          )}
          {disagree.map((d, c) =>
            d ? <rect key={c} x={labelW + c * (cell + gap) + 1} y={14} width={cell - 2} height={4} rx={2} fill="var(--warning)" /> : null,
          )}
          {rows.map((r, ri) => {
            const yy = top + ri * (cell + 8 + gap);
            return (
              <g key={r.id} onClick={() => onPick?.(r.id)} style={{ cursor: onPick ? "pointer" : undefined }}>
                {r.selected && <rect x={0} y={yy - 3} width={W} height={cell + 6} rx={6} fill="var(--wash)" />}
                <text x={6} y={yy + cell - 2} fontSize={12} fill={r.selected ? "var(--ink)" : "var(--ink-2)"} fontWeight={r.selected ? 650 : 400}>
                  {r.label}
                </text>
                {r.cells.map((ce, c) => {
                  const cx = labelW + c * (cell + gap);
                  const isH = hover?.r === ri && hover?.c === c;
                  return (
                    <g
                      key={c}
                      onPointerEnter={() => setHover({ r: ri, c })}
                      onPointerLeave={() => setHover(null)}
                      tabIndex={-1}
                    >
                      <rect x={cx - 1} y={yy - 2} width={cell + 2} height={cell + 4} fill="transparent" />
                      {ce.state === "met" && <rect x={cx} y={yy} width={cell} height={cell} rx={4} fill="var(--ink)" />}
                      {ce.state === "not" && (
                        <rect x={cx + 0.75} y={yy + 0.75} width={cell - 1.5} height={cell - 1.5} rx={4} fill="none" stroke="var(--axis)" strokeWidth={1.5} />
                      )}
                      {ce.state === "nodata" && <rect x={cx} y={yy} width={cell} height={cell} rx={4} fill="url(#hatch)" />}
                      {ce.state === "dispute" && (
                        <rect x={cx + 2.5} y={yy + 2.5} width={cell - 5} height={cell - 5} rx={1.5} fill="var(--warning)" transform={`rotate(45 ${cx + cell / 2} ${yy + cell / 2})`} />
                      )}
                      {isH && <rect x={cx - 1.5} y={yy - 1.5} width={cell + 3} height={cell + 3} rx={5} fill="none" stroke="var(--ink)" strokeWidth={1.5} />}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
        {hover && (
          <div
            className="tooltip"
            role="status"
            style={{
              left: Math.min(labelW + hover.c * (cell + gap) + 18, W - 210),
              top: top + hover.r * (cell + 8 + gap) + 18,
            }}
          >
            <div className="tt-title">
              {years[hover.c]} · {rows[hover.r].label}
            </div>
            {rows[hover.r].cells[hover.c].detail}
          </div>
        )}
      </div>
      <button className="table-toggle" onClick={() => setTable((t) => !t)} aria-expanded={table}>
        {table ? "Hide table" : "Show as table"}
      </button>
      {table && (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="sr-only">{ariaLabel}</caption>
            <thead>
              <tr>
                <th>Year</th>
                {rows.map((r) => (
                  <th key={r.id}>{r.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {years.map((yr, c) => (
                <tr key={yr}>
                  <td>
                    {yr}
                    {disagree[c] ? " ≠" : ""}
                  </td>
                  {rows.map((r) => (
                    <td key={r.id}>{STATE_TEXT[r.cells[c].state]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
