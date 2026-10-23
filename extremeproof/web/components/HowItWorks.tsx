"use client";
import { SITES } from "@/lib/sites";

const STAGES = [
  {
    when: "Before the season",
    where: "in the browser",
    title: "Compare",
    text: `Fund, cooperative and checker see what each data choice would have paid in past summers, at ${SITES.length} stations, 1966–2025.`,
    href: "#design",
  },
  {
    when: "Before the season",
    where: "on chain",
    title: "Lock",
    text: "The rule, its 122 daily thresholds and every contract term become one fingerprint. Three parties sign it; the fund's signature escrows the deposit.",
    href: "#lock",
  },
  {
    when: "During and after the season",
    where: "on chain",
    title: "Settle",
    text: "Each week a station provider and an ERA5 provider post the daily readings already published; the contract counts the hot spell against the signed thresholds and releases the share both support. Only the difference is ever disputed.",
    href: "#replay",
  },
  {
    when: "Any time later",
    where: "on your machine",
    title: "Verify",
    text: "One standard-library Python file recomputes the climate statistics from the raw data and checks every term and payment on chain.",
    href: "#verify",
  },
];

const CHANGES: [string, string, string][] = [
  ["Who decides whether the heat counted?", "The paying side, from one record and its own calculation", "The contract: named providers post the daily readings from public records named in advance, and it compares each with the threshold signed before the season"],
  ["Can the rule change after the heatwave?", "A signature shows who signed, not that no other version exists", "One fingerprint on chain; the contract refuses a different rule once locked"],
  ["What if two records disagree?", "Not visible: one source was chosen in advance", "Shown summer by summer before signing; afterwards only the difference between them is disputed, the agreed part is paid at once"],
  ["Is the money there when the rule is met?", "Paid after the payer approves", "Escrowed at lock; released only by the rule, the parties together or the fallback"],
  ["Can the community check the result?", "Only if the payer shares its model and data", "Anyone can rerun the verifier on the published bundle"],
];

/** The whole mechanism and what it changes, before the detailed steps. */
export function HowItWorks() {
  return (
    <section className="step how" id="how" aria-label="How it works">
      <div className="wrap">
        <div className="eyebrow">How it works</div>
        <h2>Agree the climate statistics before the heat. Release money as the data show it. Let anyone check.</h2>
        <ol className="how-flow">
          {STAGES.map((s, i) => (
            <li key={s.title}>
              <a href={s.href}>
                <span className="how-when">{s.when}</span>
                <strong>
                  <span className="step-num">{i + 1}</span> {s.title} <em className="chip">{s.where}</em>
                </strong>
                <span>{s.text}</span>
              </a>
            </li>
          ))}
        </ol>
        <details className="how-changes">
          <summary><h3>What changes for the people the money is for: five questions, before and after</h3></summary>
          <table>
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Question</span></th>
                <th scope="col">One record, computed by the payer</th>
                <th scope="col">ExtremeProof</th>
              </tr>
            </thead>
            <tbody>
              {CHANGES.map(([q, before, after]) => (
                <tr key={q}>
                  <th scope="row">{q}</th>
                  <td>{before}</td>
                  <td>{after}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
        <div className="how-impact" aria-label="Real-world impact">
          <h3>Real-world impact</h3>
          <p className="callout impact-headline">
            <strong>Money during the heatwave, not months after it.</strong> Replaying 2021–2025 at our 10 Turkish stations under the default rule: in the 19
            summers where both records supported a payment, <strong>96% of that money would have been released before the season ended</strong>, in 10 of
            them by the end of July. Weekly checks, assuming data are published 5 days late; pinned final data, revisions not modelled.
          </p>
          <div className="grid-3">
            <div className="fact">
              <strong>Heat already costs farmers here</strong>
              <p className="small">
                In September 2021 Türkiye's state-backed farm insurance pool reported paying 214 million lira to 14,213 producers for drought losses
                (<a href="https://www.meinsurancereview.com/News/View-NewsLetter-Article/id/77954/Type/MiddleEast" target="_blank" rel="noreferrer">MEIR</a>);
                since 2021 the pool also covers heat damage to citrus (<a href="https://www.milliyet.com.tr/ekonomi/narenciyede-sicaklik-zararinin-tarsim-kapsamina-alinmasi-sevindirdi-6365476" target="_blank" rel="noreferrer">AA</a>).
                The Ministry of Agriculture names Adana, Antalya, Hatay and Mersin as the leading orange provinces (<a href="https://arastirma.tarimorman.gov.tr/tepge/Belgeler/PDF%20Tar%C4%B1m%20%C3%9Cr%C3%BCnleri%20Piyasalar%C4%B1/2024-Temmuz%20Tar%C4%B1m%20%C3%9Cr%C3%BCnleri%20Raporu/Portakal%20Tar%C4%B1m%20%C3%9Cr%C3%BCnleri%20Piyasalar%C4%B1%20Raporu%20Temmuz-2024-v4.pdf" target="_blank" rel="noreferrer">TEPGE 2024</a>): five of our ten stations are there (Adana, Antalya, Finike, İskenderun in Hatay, Mersin).
              </p>
            </div>
            <div className="fact">
              <strong>Who could use it now</strong>
              <p className="small">
                Red Cross societies already run heatwave protocols that release money when a threshold is crossed: Greece in 2024, Kyrgyzstan in 2025 (<a href="https://www.climatecentre.org/13968/hellenic-red-cross-acts-ahead-of-extreme-heat-in-greece/" target="_blank" rel="noreferrer">Climate Centre</a>,{" "}
                <a href="https://go-api.ifrc.org/api/downloadfile/91065/MDRKG016_eapar" target="_blank" rel="noreferrer">IFRC</a>). Relief funds, insurance pools and cooperatives that pay
                on a heat index face the same question: whose record, which normal, what if they disagree. ExtremeProof answers it before signing and proves it after.
              </p>
            </div>
            <div className="fact">
              <strong>How it scales</strong>
              <p className="small">
                The rule needs only a station ID and a grid point: GHCN-Daily and ERA5 are free and global, so the same engine runs for any place with a station
                record, as the 10-station scan shows. One agreement is a handful of transactions; checking it is one standard-library Python file. Adaptation, not
                mitigation: it does not cut emissions, it makes heat relief arrive by a rule people can check.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
