import { COMPARISON_YEARS, compareSeason, decisionText, ruleFromSpec } from "./comparison";
import type { SiteData } from "./rule";
import { purposeText } from "./finder";

// A one-page, plain-language summary of a written rule, for the cooperative's
// members to read before their representative signs. Every value comes from the
// spec text and the same comparison module as the page; nothing is typed in.

const esc = (s: unknown) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const units = (cents: number) => (cents / 100).toLocaleString("en-US");

const FILL: Record<string, [string, string]> = {
  none: ["left empty", "boş bırakılır"],
  era5_quantile_map: ["filled from ERA5, adjusted to the station's own distribution (quantile mapping)", "ERA5'ten, istasyonun kendi dağılımına göre düzeltilerek doldurulur (quantile mapping)"],
  era5_monthly_linear: ["filled from ERA5 with a monthly linear correction", "ERA5'ten aylık doğrusal düzeltmeyle doldurulur"],
  era5_raw: ["filled with uncorrected ERA5 values", "düzeltilmemiş ERA5 değerleriyle doldurulur"],
};

export function memberSheet(spec: any, hash: string, d: SiteData): string {
  // Turkish alongside English for sites in Türkiye; English only elsewhere.
  const turkish = (spec.site.country ?? "TR") === "TR";
  const bi = (en: string, tr: string) => (turkish ? `${en} · ${tr}` : en);
  const r = spec.rule;
  const st = spec.settlement;
  const year = spec.observation_year;
  const base = `${r.base_period[0].slice(0, 4)}–${r.base_period[1].slice(0, 4)}`;
  const amount = units(st.amount_cents);
  const fill = FILL[spec.sources.find((s: any) => s.id === "station")?.fill?.method ?? "none"] ?? FILL.none;
  const fallbackEn = st.on_dispute === "pay" ? "the money is paid to the cooperative" : "the money goes back to the fund";
  const fallbackTr = st.on_dispute === "pay" ? "para kooperatife ödenir" : "para fona geri döner";
  const rule = ruleFromSpec(spec);
  const ladder: [number, number][] = st.payout_ladder ?? [[r.min_spell_days, 10000]];
  const graded = ladder.length > 1;
  const ladderEn = ladder.map(([d, b]) => `${units((st.amount_cents * b) / 10000)} DEMO (${b / 100}%) for ${d}+ days`).join("; ");
  const ladderTr = ladder.map(([d, b]) => `art arda ${d}+ gün için ${units((st.amount_cents * b) / 10000)} DEMO (%${b / 100})`).join("; ");
  const past = COMPARISON_YEARS.map((y) => compareSeason(d, rule, y, st.amount_cents));
  const top = 100 - r.percentile;
  const topTr = `%${top}'${top === 10 ? "luk" : "lik"}`; // on → 'luk, beş → 'lik
  const rows = past
    .map((s) => {
      const p = s.policies.dual;
      const why = p.reason === "disagreement" ? bi("records disagree", "kayıtlar çelişiyor") : p.reason === "missing" ? bi("too little data", "veri yetersiz") : bi("records agree", "kayıtlar uyumlu");
      return `<tr><td>${s.year}${s.year === year ? " ← this agreement's season (demo replay)" : ""}</td><td>${esc(decisionText(p))}</td><td>${why}</td><td>${units(p.payoutCents)}</td></tr>`;
    })
    .join("");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(spec.site.name)} ${year} heat relief agreement: summary for members</title>
<style>
  body { font: 15px/1.5 system-ui, "Segoe UI", sans-serif; color: #111; background: #fff; max-width: 820px; margin: 24px auto; padding: 0 16px; }
  h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 16px; margin: 22px 0 6px; border-bottom: 1px solid #ddd; padding-bottom: 3px; }
  .tr { color: #444; } .tr::before { content: "TR · "; font-weight: 700; color: #888; font-size: 12px; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; } th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid #e3e3e3; vertical-align: top; }
  th { background: #f4f4f2; font-size: 12.5px; } code { font: 12px ui-monospace, Consolas, monospace; word-break: break-all; }
  .box { border: 1px solid #ccc; border-radius: 8px; padding: 10px 14px; } .muted { color: #666; font-size: 13px; }
  @media print { body { margin: 0; } a { color: inherit; } }
  body.en .tr { display: none; }
</style></head><body${turkish ? "" : ' class="en"'}>
<p class="muted">ExtremeProof · ${bi("draft for discussion before signing", "imza öncesi görüşme taslağı")}</p>
<h1>${esc(spec.site.name)}, summer ${year}: heat relief agreement</h1>
<p class="tr">${esc(spec.site.name)}, ${year} yazı: sıcak hava yardımı anlaşması</p>

<h2>1. ${bi("What it pays", "Ne öder")}</h2>
${graded
    ? `<p>Up to ${amount} DEMO to the cooperative's account, more for a longer heatwave: ${ladderEn}. DEMO are demonstration units, not money.</p>
<p class="tr">Kooperatifin hesabına en fazla ${amount} DEMO ödenir; sıcak hava dalgası uzadıkça ödeme artar: ${ladderTr}. DEMO gösterim birimidir, gerçek para değildir.</p>`
    : `<p>${amount} DEMO to the cooperative's account, once. DEMO are demonstration units, not money.</p>
<p class="tr">Kooperatifin hesabına bir kez ${amount} DEMO ödenir. DEMO gösterim birimidir, gerçek para değildir.</p>`}

<h2>2. ${bi("When it pays", "Ne zaman öder")}</h2>
<p><strong>During the summer:</strong> providers check weekly, assuming data are published 5 days late. The share both support is released at the next check after publication; an operator must submit the transaction. This is modelled timing, not a delivery guarantee. The rest is settled after 30 September.</p>
<p class="tr"><strong>Yaz içinde:</strong> sağlayıcılar haftalık kontrol yapar; verilerin 5 gün gecikmeyle yayımlandığı varsayılır. İkisinin de desteklediği tutar yayımdan sonraki kontrolde serbest bırakılır; bir operatörün işlemi göndermesi gerekir. Bu süre bir modeldir, ödeme garantisi değildir. Kalanı 30 Eylül'den sonra kesinleşir.</p>
<p>If, between 1 June and 30 September ${year}, the daily maximum temperature is above the hottest ${top}% for that calendar day,
measured against the ${base} climate of this place, on at least <strong>${r.min_spell_days} days in a row</strong>.</p>
<p class="tr">1 Haziran – 30 Eylül ${year} arasında günlük en yüksek sıcaklık, bu yerin ${base} iklimine göre o takvim günü için en sıcak ${topTr} dilimin
üzerinde <strong>art arda en az ${r.min_spell_days} gün</strong> kalırsa.</p>

${spec.purpose ? `<p class="box">${esc(purposeText(spec.purpose))}<br><span class="tr">Amaç: yedek kuralla yapılan ödemeler dahil yaklaşık ${spec.purpose.target_return_period_summers} yazda bir ödeme. İmza anında bu kural ${spec.purpose.calibration_window.join("–")} arasındaki ${spec.purpose.summers} yazın ${spec.purpose.final_pays} tanesinde ödeme yapardı; bunların ${spec.purpose.agreement_pays} tanesi iki kaynağın uyuşmasıyla.</span></p>` : ""}

<h2>3. ${bi("Who measures", "Kim ölçer")}</h2>
<p>Two separate data providers post that summer's daily readings. The contract compares each with the threshold for that day fixed today, and counts the heatwave itself; a day once posted cannot be changed:</p>
<ul>
  <li>A: the ${esc(spec.site.name)} weather station (${esc(spec.site.station)}). Missing days are ${fill[0]}. If more than ${r.max_filled_days} days had to be filled, or more than ${r.max_missing_days} days are still missing after filling, this provider gives no answer.</li>
  <li>B: ERA5, a reconstruction of past weather from observations and a weather model (Copernicus/ECMWF).</li>
</ul>
<p class="tr">İki ayrı veri sağlayıcı o yazın günlük ölçümlerini yayımlar. Sözleşme her ölçümü bugün belirlenen o günün eşiğiyle karşılaştırır ve sıcak hava dalgasını kendisi sayar; yayımlanan bir gün sonradan değiştirilemez. A: ${esc(spec.site.name)} meteoroloji istasyonu; eksik günler ${fill[1]}. ${r.max_filled_days} günden fazlasının doldurulması gerekirse veya doldurmadan sonra ${r.max_missing_days} günden fazla eksik kalırsa bu sağlayıcı cevap vermez.
B: ERA5, gözlemler ve hava modeliyle yeniden oluşturulmuş geçmiş hava verisi. A, B'nin verisini eksik günleri doldurmak için kullandığından ikisi tamamen bağımsız değildir.</p>
<p class="muted">Provider A fills gaps with ERA5, B's source, so the two are not fully independent.</p>

<h2>4. ${bi("What happens", "Ne olur")}</h2>
<table><thead><tr><th>${bi("Both providers say", "İki sağlayıcı")}</th><th>${bi("Result", "Sonuç")}</th></tr></thead><tbody>
<tr><td>${bi("The rule was met", "Koşul gerçekleşti")}</td><td>${graded ? bi("The amount for the heatwave length both report is paid at once", "ikisinin de bildirdiği uzunluğa karşılık gelen tutar hemen ödenir") : bi(`${amount} DEMO paid to the cooperative`, "kooperatife ödenir")}</td></tr>
<tr><td>${bi("The rule was not met", "Koşul gerçekleşmedi")}</td><td>${bi("The deposit goes back to the fund", "para fona döner")}</td></tr>
<tr><td>${bi("They disagree, or one has too little data", "Çelişki veya eksik veri")}</td><td>${graded ? bi("The part both support is paid and the part neither supports goes back at once; only the difference is in question.", "İkisinin de desteklediği kısım hemen ödenir, hiçbirinin desteklemediği kısım hemen geri döner; yalnızca fark tartışmalıdır.") + "<br>" : ""}The fund, the cooperative and the checker can decide together. If they do not all agree within 30 days, ${fallbackEn}.<br><span class="tr">Fon, kooperatif ve denetçi birlikte karar verebilir. 30 gün içinde oybirliği olmazsa ${fallbackTr}.</span></td></tr>
</tbody></table>

<h2>5. ${bi("This rule in recent summers", "Bu kural son yazlarda")}</h2>
<table><thead><tr><th>${bi("Summer", "Yaz")}</th><th>${bi("Result", "Sonuç")}</th><th>${bi("Why", "Neden")}</th><th>DEMO</th></tr></thead><tbody>${rows}</tbody></table>
<p class="muted">Recomputed from the pinned GHCN-Daily and ERA5 files. A look back, not a forecast.</p>

<h2>6. ${bi("What cannot change", "Değiştirilemeyen")}</h2>
<div class="box"><p>${bi("Fingerprint of the full agreement text", "Anlaşma metninin parmak izi")} (sha256):<br><code>${esc(hash)}</code></p>
<p>After the fund, the cooperative and the checker have signed this fingerprint, nobody can change the rule. Before signing, compare this number with the one on the screen.</p>
<p class="tr">Fon, kooperatif ve denetçi bu parmak izini imzaladıktan sonra kural kimse tarafından değiştirilemez. İmzadan önce bu numarayı ekrandakiyle karşılaştırın.</p></div>

<h2>7. ${bi("How to check afterwards", "Sonradan nasıl kontrol edilir")}</h2>
<p>Anyone can download the verification bundle and run one Python file (<code>python verify.py bundle.zip</code>). It recomputes the result from the raw data.</p>
<p class="tr">Herkes doğrulama paketini indirip tek bir Python dosyasını çalıştırabilir. Sonuç ham veriden yeniden hesaplanır.</p>

<p class="muted">Not insurance. ${bi("A blockchain does not make the data true: if every record is wrong, the payment is wrong.", "Sigorta değildir. Tüm kayıtlar yanlışsa ödeme de yanlış olur.")}</p>
</body></html>`;
}
