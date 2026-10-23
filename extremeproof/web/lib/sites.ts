// The pinned GHCN stations with precomputed tables in public/data/<id>.json.
// Mirrors SITES in climate/specs.py and scripts/build_web_data.py. Antalya and
// Muğla are the worked examples; the others feed the regional scan.
export const SITES: { id: string; name: string; station: string; featured?: boolean }[] = [
  { id: "antalya", name: "Antalya", station: "TUM00017300", featured: true },
  { id: "mugla", name: "Muğla", station: "TUM00017292", featured: true },
  { id: "izmir", name: "İzmir", station: "TUM00017220" },
  { id: "finike", name: "Finike", station: "TU000017375" },
  { id: "isparta", name: "Isparta", station: "TU000017240" },
  { id: "afyon", name: "Afyon", station: "TUM00017190" },
  { id: "konya", name: "Konya", station: "TUM00017244" },
  { id: "mersin", name: "Mersin", station: "TUM00017340" },
  { id: "adana", name: "Adana", station: "TUW00033308" },
  { id: "iskenderun", name: "İskenderun", station: "TUM00017370" },
];
export const FEATURED = SITES.filter((s) => s.featured).map((s) => s.id);
