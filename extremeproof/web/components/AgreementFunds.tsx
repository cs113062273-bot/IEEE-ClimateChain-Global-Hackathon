"use client";
import { fmtDemo, type AgreementView } from "@/lib/chain";

/** Only this agreement's money. A live season's unspent escrow is not a refund. */
export function AgreementFunds({ ag, id }: { ag: AgreementView; id: bigint }) {
  const funded = (ag.approvals & 1) !== 0;
  const finished = ["Paid", "Refunded", "Cancelled"].includes(ag.status);
  const held = !funded || finished ? 0n : ag.status === "Disputed" ? ag.contested : ag.amount - ag.paidOut;
  const returned = funded && (finished || ag.status === "Disputed") ? ag.amount - ag.paidOut - held : 0n;
  const parts = [
    { cls: "paid", label: "Paid to cooperative", v: ag.paidOut },
    { cls: ag.status === "Disputed" ? "held" : "escrow", label: ag.status === "Disputed" ? "Held in dispute" : "Still in escrow", v: held },
    { cls: "back", label: "Returned to fund", v: returned },
    { cls: "unfunded", label: "Awaiting deposit", v: funded ? 0n : ag.amount },
  ];
  return <section className="agreement-funds" aria-label={`Money in agreement ${id}`} aria-live="polite">
    <div className="eyebrow">Agreement #{String(id)} · {fmtDemo(ag.amount)}</div>
    <h3>Where this deposit is now</h3>
    <div className="deposit-bar" aria-hidden="true">
      {parts.filter((p) => p.v > 0n).map((p) => <i key={p.cls} className={p.cls} style={{ width: `${Number(p.v) / Number(ag.amount) * 100}%` }} />)}
    </div>
    <dl className="funds-values">
      {parts.filter((p) => p.cls !== "unfunded" || p.v > 0n).map((p) => <div key={p.cls}><dt><i className={p.cls} />{p.label}</dt><dd>{fmtDemo(p.v)}</dd></div>)}
    </dl>
    <p className="note">{ag.status === "Proposed" ? "The agreement locks only when all three parties sign."
      : ag.status === "Locked" ? "The agreement remains locked. Unreleased money stays in escrow; it has not been returned to the fund."
      : ag.status === "Disputed" ? `Only ${fmtDemo(held)} awaits a unanimous decision. Without one, the signed fallback will ${ag.onDispute === "pay" ? "pay the cooperative" : "return it to the fund"}.`
      : "Settlement complete. These amounts belong to this agreement alone."}</p>
  </section>;
}
