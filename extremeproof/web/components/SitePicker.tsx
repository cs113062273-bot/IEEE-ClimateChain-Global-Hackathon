"use client";
import { COUNTRY, SITES } from "@/lib/sites";

const featured = SITES.filter((s) => s.featured);
const others = SITES.filter((s) => !s.featured);

/** The two worked examples as buttons, the other pinned stations in a list. */
export function SitePicker({ site, setSite, label }: { site: string; setSite: (s: string) => void; label: string }) {
  const isOther = others.some((s) => s.id === site);
  return (
    <div className="site-picker">
      <div className="seg" role="group" aria-label={label}>
        {featured.map((s) => (
          <button key={s.id} aria-pressed={site === s.id} onClick={() => setSite(s.id)}>
            {s.name}
          </button>
        ))}
      </div>
      <select aria-label={`${label}: other stations`} className={isOther ? "active" : ""} value={isOther ? site : ""} onChange={(e) => e.target.value && setSite(e.target.value)}>
        <option value="">{SITES.length - featured.length} more stations…</option>
        {Object.entries(COUNTRY).map(([code, country]) => (
          <optgroup key={code} label={country}>
            {others.filter((s) => s.country === code).map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}
