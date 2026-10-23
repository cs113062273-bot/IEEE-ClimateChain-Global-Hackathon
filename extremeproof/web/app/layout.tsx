import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ExtremeProof",
  description:
    "Pre-arranged heatwave relief whose trigger is computed from a place's own climate normal, fixed before the season, settled by independent data providers and checkable by anyone.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
