"""Produce v2 source sub-bundles from externally pinned upstream snapshots.

The evidence never creates its own trust root. The standalone verifier reads the
separately distributed trust manifest and reconstructs input values independently.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
ANCHORS_PATH=ROOT/"data/trust/source_anchors.v1.json"
TRANSFORM_CONFIG={
    "version":"gridproof-input-transforms-v1",
    "interval_minutes":30,"timezone":"UTC","ci_interval":"portal_datetime_is_interval_start",
    "weather_model":"ERA5","radiation_alignment":"preceding_hour_at_h_plus_1_split_constant_halfhours",
    "pv_outcome":{"formula":"kwp*0.5*0.8*clip(radiation/1000,0,1)","performance_ratio":0.8},
    "pv_decision":{"formula":"calendar-sine-v1","daylight_base_hours":12,"daylight_amplitude_hours":4,"season_base":0.58,"season_amplitude":0.2,"phase_day":80,"period_days":365},
    "fixed_load":{"formula":"0.5*(6+8*(8<=midpoint_utc_hour<18)+2*(18<=midpoint_utc_hour<22))","data_origin":"synthetic"},
    "tariff":{"formula":"0.12 if midpoint_utc_hour<7 else 0.36 if 16<=hour<20 else 0.23","data_origin":"illustrative_utc_tariff"},
    "forecast_features":"past-only-carbon-calendar-15-features-v1",
    "actual_availability_assumption":"Past actual timestamps assumed available at midnight; publication latency/revisions not archived",
}


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def packed_blob(body):
    """Deterministic bounded transport; trusted SHA always covers original bytes."""
    packed=bytearray(gzip.compress(body,compresslevel=9,mtime=0))
    packed[9]=255  # Normalize gzip OS header for portable byte determinism.
    return base64.b64encode(packed).decode("ascii")


def _trusted_bytes(anchor):
    for relative in anchor["paths"]:
        path=(ROOT/relative).resolve()
        if ROOT.resolve() not in path.parents:raise ValueError("Trusted source path outside project")
        if path.exists():
            body=path.read_bytes()
            if hashlib.sha256(body).hexdigest()!=anchor["sha256"]:
                raise ValueError(f"Source differs from external anchor: {relative}")
            return body
    raise ValueError(f"Necessary pinned source unavailable: {anchor['source_id']}")


def portable_predict(model,features):
    # This independent implementation does not import backend or deserialize pickle.
    from scripts.verify_evidence import portable_predict as independent_predict
    return independent_predict(model,features)


def build_lineage(run,canonical_encoder):
    if not ANCHORS_PATH.exists():raise ValueError("Trusted upstream anchor manifest is unavailable")
    anchors=json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
    blobs=[]
    for sid in ["neso-national-ci-2025","openmeteo-london-weather-2025"]:
        anchor=anchors["sources"][sid]
        body=_trusted_bytes(anchor)
        blobs.append({"source_id":sid,"encoding":"gzip+base64","sha256":anchor["sha256"],"body":packed_blob(body),"source_url":anchor["source_url"],"license":anchor["license"]})
    model_blob=None
    if run["forecast_model"]["version"]=="lightgbm-past-only-v1":
        anchor=anchors["models"]["lightgbm-past-only-v1"]
        body=_trusted_bytes(anchor)
        model_blob={"source_id":anchor["source_id"],"encoding":"gzip+base64","sha256":anchor["sha256"],"body":packed_blob(body)}
    configuration={"scenario":run["scenario"],"transform_config":TRANSFORM_CONFIG,"forecast_model":run["forecast_model"],"carbon_weight":run["carbon_weight"]}
    encoded=canonical_encoder(configuration)
    scenario_sha=hashlib.sha256(canonical_encoder(run["scenario"])).hexdigest()
    return {"version":"gridproof-source-lineage-v2","trusted_anchor_manifest_sha256":file_sha(ANCHORS_PATH),
            "source_blobs":blobs,"model_blob":model_blob,"configuration":configuration,
            "configuration_sha256":hashlib.sha256(encoded).hexdigest(),"scenario_sha256":scenario_sha,
            "trust_boundary":"Separate trusted upstream hashes bind original snapshot bytes; neither the report nor blockchain proves provider measurement truth."}


def verify_lineage(evidence,root=ROOT,expected_config_digest=None):
    from scripts.verify_evidence import verify_lineage as independent_verify
    return independent_verify(evidence,Path(root),expected_config_digest=expected_config_digest)
