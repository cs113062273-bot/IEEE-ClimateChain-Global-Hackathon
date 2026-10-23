import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GridProof · Workplace charging",
  description: "Meet more drivers' charging requests before they leave, on the connection you already have: departure-risk-aware charging, replayed on real held-out sessions, with an independently checkable record.",
};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
