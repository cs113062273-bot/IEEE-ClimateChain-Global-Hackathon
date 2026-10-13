import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GridProof · Carbon-aware orchestration",
  description: "Reproduce campus energy decisions using authentic GB grid data, a simulated microgrid, and verifiable evidence.",
};
export default function RootLayout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
