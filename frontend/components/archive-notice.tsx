import Link from "next/link";

/** Shown on earlier prototypes that are kept for their recorded proofs and tests, not as the product. */
export function ArchiveNotice({what}: {what: string}) {
  return <div role="note" style={{background: "#fff4d6", color: "#3d2e00", borderBottom: "1px solid #e8cf86", padding: "10px 16px", fontSize: 13, lineHeight: 1.45, fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif"}}>
    <b>Archived earlier prototype: {what}.</b> It uses a synthetic two-vehicle campus and its results are not the current product&apos;s claims. Kept for reproducibility of earlier reports.{" "}
    <Link href="/" style={{color: "#3d2e00", textDecoration: "underline", fontWeight: 600}}>Open the current workplace charging product →</Link>
  </div>;
}
