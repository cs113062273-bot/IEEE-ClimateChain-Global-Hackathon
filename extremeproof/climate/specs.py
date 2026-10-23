"""Build trigger specs for the demo sites from the pinned data.

The spec is the full agreement text the three parties sign: the climate rule,
the history that exists at signing (pinned by sha256), each source's daily
thresholds for the season computed from it, where each source's
observation-year data will be fetched after the season, and every setting the
contract will execute (parties, token, amount, quorum, providers per data
source, windows and deadlines, dispute fallback). The verifier checks each of
these against the chain, so the document and the contract cannot silently
diverge.
"""
import hashlib
import json

from eth_utils import keccak

from . import archive as A
from .trigger import ON_DISPUTE, ROOT, SPEC_SCHEMA, contract_timing, payout_ladder, season_normal

SITES = {
    "antalya": {"id": "antalya", "name": "Antalya", "country": "TR", "station": "TUM00017300"},
    "mugla": {"id": "mugla", "name": "Muğla", "country": "TR", "station": "TUM00017292"},
    "izmir": {"id": "izmir", "name": "İzmir", "country": "TR", "station": "TUM00017220"},
    "finike": {"id": "finike", "name": "Finike", "country": "TR", "station": "TU000017375"},
    "isparta": {"id": "isparta", "name": "Isparta", "country": "TR", "station": "TU000017240"},
    "afyon": {"id": "afyon", "name": "Afyon", "country": "TR", "station": "TUM00017190"},
    "konya": {"id": "konya", "name": "Konya", "country": "TR", "station": "TUM00017244"},
    "mersin": {"id": "mersin", "name": "Mersin", "country": "TR", "station": "TUM00017340"},
    "adana": {"id": "adana", "name": "Adana", "country": "TR", "station": "TUW00033308"},
    "iskenderun": {"id": "iskenderun", "name": "İskenderun", "country": "TR", "station": "TUM00017370"},
}


def manifest():
    return json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["files"]


def _grid(sid):
    """The ERA5 grid point the pinned download was requested for (the observation-year fetch asks for the same)."""
    url = manifest()[A.raw_file("open_meteo", sid)]["url"]
    q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
    return q["latitude"], q["longitude"]


def normal_keccak(values):
    """keccak256(abi.encodePacked(int32[])) as TriggerAgreement stores it; zero when there is no normal."""
    if values is None:
        return "0x" + "00" * 32
    return "0x" + keccak(b"".join(v.to_bytes(32, "big", signed=True) for v in values)).hex()


def make_spec(site="antalya", year=2024, base=(1961, 1990), percentile=90, min_spell_days=6,
              season=("06-01", "09-30"), fill_method="era5_quantile_map", max_missing_days=0,
              max_filled_days=122, min_base_coverage_permille=600, quorum=2, on_dispute="refund",
              amount_cents=5_000_000, parties=None, providers=None, token=None, chain_id=None, contract=None,
              purpose=None, payout="flat", payout_steps=None):
    """``parties``/``providers``/``token``/``contract`` are addresses; when given, the verifier checks them on chain."""
    if on_dispute not in ON_DISPUTE:
        raise ValueError(f"on_dispute must be one of {ON_DISPUTE}")
    site_info = SITES[site]
    sid = site_info["station"]
    grid = _grid(sid)

    def source(id_, kind, **extra):
        name = A.history_name(kind, sid, year)
        start, end = f"{year}-01-01", f"{year}-{season[1]}"
        return {"id": id_, "kind": kind, "station": sid, **extra,
                "history": {"file": name, "through": f"{year - 1}-12-31",
                            "sha256": hashlib.sha256(A.read_logical(ROOT, name)).hexdigest()},
                "season_data": {"from": start, "to": end, "publisher": A.PUBLISHERS[kind],
                                "url": A.season_url(kind, sid, start, end, grid), "fetched": "by the provider after the season ends"}}

    station = source("station", "ghcn_daily")
    era5 = source("era5", "open_meteo", model="era5")
    if fill_method != "none":
        station["fill"] = {"method": fill_method, "from": "era5", "fit_period": ["1963-01-01", f"{year - 1}-12-31"]}
    settlement = {
        "quorum": quorum,
        "providers": 2,
        "on_dispute": on_dispute,
        "amount_cents": amount_cents,
        # spell length -> share of the deposit; the part both providers support is paid at once
        "payout_ladder": payout_ladder(min_spell_days, payout, payout_steps),
        "unit": "DEMO (demo relief units, not money)",
        "timing": contract_timing(year, season),
    }
    if parties:
        settlement["parties"] = {k: parties[k].lower() for k in ("funder", "community", "checker", "beneficiary")}
    if providers:
        settlement["provider_addresses"] = {k: providers[k].lower() for k in ("station", "era5")}
    if token:
        settlement["token"] = token.lower()
    if contract:
        settlement["contract"] = contract.lower()
    if chain_id is not None:
        settlement["chain_id"] = chain_id
    spec = {
        "schema": SPEC_SCHEMA,
        "title": f"{site_info['name']} summer heat spell {year}",
        "site": site_info,
        "rule": {
            "kind": "heat_spell",
            "variable": "TX",
            "base_period": [f"{base[0]}-01-01", f"{base[1]}-12-31"],
            "percentile": percentile,
            "percentile_window_days": 5,
            "quantile_method": "hyndman_fan_type8",
            "season": list(season),
            "min_spell_days": min_spell_days,
            "min_base_coverage_permille": min_base_coverage_permille,
            "max_missing_days": max_missing_days,
            "max_filled_days": max_filled_days,
        },
        "observation_year": year,
        "sources": [station, era5],
        "settlement": settlement,
    }
    # The climate statistics, signed before the season: each source's daily thresholds, in
    # thousandths of a degree; the contract stores their keccak fingerprint and checks every
    # reading a provider posts against them.
    for s in spec["sources"]:
        s["season_normal_mdegc"] = season_normal(s, spec["rule"], year)
    settlement["normal_keccak"] = {s["id"]: normal_keccak(s["season_normal_mdegc"]) for s in spec["sources"]}
    if purpose is not None:  # signed intent: target return period and the calibration the parties saw
        spec["purpose"] = purpose
    return spec
