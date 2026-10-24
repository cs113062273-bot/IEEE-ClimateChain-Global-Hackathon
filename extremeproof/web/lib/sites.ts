// The pinned GHCN stations with precomputed tables in public/data/<id>.json.
// Mirrors SITES in climate/specs.py and scripts/build_web_data.py. Antalya and
// Muğla are the worked examples; the others feed the regional scan.
export const SITES: { id: string; name: string; station: string; country: string; featured?: boolean }[] = [
  { id: "antalya", name: "Antalya", station: "TUM00017300", country: "TR", featured: true },
  { id: "mugla", name: "Muğla", station: "TUM00017292", country: "TR", featured: true },
  { id: "izmir", name: "İzmir", station: "TUM00017220", country: "TR" },
  { id: "finike", name: "Finike", station: "TU000017375", country: "TR" },
  { id: "isparta", name: "Isparta", station: "TU000017240", country: "TR" },
  { id: "afyon", name: "Afyon", station: "TUM00017190", country: "TR" },
  { id: "konya", name: "Konya", station: "TUM00017244", country: "TR" },
  { id: "mersin", name: "Mersin", station: "TUM00017340", country: "TR" },
  { id: "adana", name: "Adana", station: "TUW00033308", country: "TR" },
  { id: "iskenderun", name: "İskenderun", station: "TUM00017370", country: "TR" },
  // The same engine outside Türkiye (summer clocks also UTC+3).
  { id: "athens", name: "Athens", station: "GR000016716", country: "GR" },
  { id: "larissa", name: "Larissa", station: "GR000016648", country: "GR" },
  { id: "bucharest", name: "Bucharest", station: "ROE00108889", country: "RO" },
  { id: "sofia", name: "Sofia", station: "BUM00015614", country: "BG" },
];
export const COUNTRY: Record<string, string> = { TR: "Türkiye", GR: "Greece", RO: "Romania", BG: "Bulgaria" };
export const IN_TURKIYE = SITES.filter((s) => s.country === "TR");
export const FEATURED = SITES.filter((s) => s.featured).map((s) => s.id);
