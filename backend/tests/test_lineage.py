"""Attack regressions against source lineage, independent of internal arithmetic."""
from __future__ import annotations
import base64
import gzip
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from backend.app.domain.schemas import OptimizeRequest,Scenario
from backend.app.services.simulator import compare
from backend.app.services.evidence import make_evidence,verify_evidence,digest
from backend.app.services.data import ROOT
from scripts.verify_evidence import inspect,verify_lineage,portable_predict
import scripts.verify_evidence as independent_verifier


@pytest.fixture(scope="module")
def proof():
    return make_evidence(compare(OptimizeRequest(date="2025-09-01"))["run_id"])


def rehash(e):
    e["input_sha256"]=digest(e["inputs"])
    return "0x"+digest(e)


def both(e,expected,root=ROOT):
    a=verify_evidence(e,expected,check_local_files=False)
    b=inspect(e,expected,root,check_local_files=False)
    return a,b


def test_valid_v2_reconstructs_trained_model_and_all_fields(proof):
    for result in both(proof["evidence"],proof["digest"]):
        assert result["verified"] and result["status"]=="VERIFIED",result["errors"]
        assert all(result["levels"][k]["verified"] for k in ["integrity","source_lineage","physical_validity"])
        assert result["levels"]["onchain_attestation"]["status"]=="NOT_CHECKED"
        assert all(x["representation"].startswith("embedded") for x in result["levels"]["source_lineage"]["source_checks"])
    roles={s["source_id"]:s["role"] for s in proof["evidence"]["source_snapshots"]}
    assert "neso-demand-2025" not in roles and "pvgis-london-pv-model-2023" not in roles
    assert roles["gridproof-carbon-model-lightgbm-v1"]=="decision_model"


def test_zero_ci_new_digest_does_not_certify_fabricated_source_values(proof):
    e=copy.deepcopy(proof["evidence"])
    for key in ["intervals","dispatch","baseline_dispatch"]:
        for x in e["inputs"][key]:x["ci_actual_g_per_kwh"]="0.000000000"
    for key in ["plan_kgco2","baseline_kgco2","difference_kgco2"]:e["results"][key]="0.000000000"
    for result in both(e,rehash(e)):
        assert result["levels"]["integrity"]["verified"]
        assert result["levels"]["physical_validity"]["verified"]
        assert not result["verified"] and result["levels"]["source_lineage"]["status"]=="MISMATCH"
        assert any("ci_actual" in x for x in result["errors"])


@pytest.mark.parametrize("field,value",[("shortwave_radiation_w_per_m2","0"),("solar_outcome_kwh","123"),("pv_forecast_kwh","0"),("ci_forecast_g_per_kwh","0"),("fixed_load_kwh","1"),("tariff_gbp_per_kwh","0")])
def test_consistent_rewritten_inputs_fail_original_source_reconstruction(proof,field,value):
    e=copy.deepcopy(proof["evidence"])
    for key in ["intervals","dispatch","baseline_dispatch"]:
        for x in e["inputs"][key]:x[field]=value
    for result in both(e,rehash(e)):
        assert not result["verified"]
        assert not result["levels"]["source_lineage"]["verified"]


def test_original_blob_rewrite_and_self_declared_new_hash_do_not_replace_trust_anchor(proof):
    e=copy.deepcopy(proof["evidence"])
    blob=e["lineage"]["source_blobs"][0]
    raw=base64.b64decode(blob["body"])
    body=json.loads(gzip.decompress(raw) if blob["encoding"]=="gzip+base64" else raw)
    for r in body["result"]["records"]:r["actual"]=0
    encoded=json.dumps(body).encode();blob["body"]=base64.b64encode(encoded).decode();blob["encoding"]="base64"
    import hashlib
    blob["sha256"]=hashlib.sha256(encoded).hexdigest()
    for result in both(e,rehash(e)):
        assert not result["verified"]
        assert any("trusted anchor" in x for x in result["errors"])


def test_missing_original_sources_or_external_anchor_is_incomplete(proof,tmp_path):
    trust=tmp_path/"data/trust";trust.mkdir(parents=True)
    shutil.copyfile(ROOT/"data/trust/source_anchors.v1.json",trust/"source_anchors.v1.json")
    e=copy.deepcopy(proof["evidence"]);e["lineage"]["source_blobs"]=[]
    result=inspect(e,rehash(e),tmp_path,check_local_files=False)
    assert not result["verified"] and result["status"]=="INCOMPLETE"
    assert result["levels"]["source_lineage"]["status"]=="INCOMPLETE"
    # Embedded authentic sources suffice without any bulk files, but not without external pins.
    result=inspect(proof["evidence"],proof["digest"],tmp_path,check_local_files=False)
    assert result["verified"]
    (trust/"source_anchors.v1.json").unlink()
    result=inspect(proof["evidence"],proof["digest"],tmp_path,check_local_files=False)
    assert not result["verified"] and result["status"]=="INCOMPLETE"


def test_missing_portable_model_cannot_claim_forecast_reconstruction(proof,tmp_path):
    trust=tmp_path/"data/trust";trust.mkdir(parents=True)
    shutil.copyfile(ROOT/"data/trust/source_anchors.v1.json",trust/"source_anchors.v1.json")
    e=copy.deepcopy(proof["evidence"]);e["lineage"]["model_blob"]=None
    result=inspect(e,rehash(e),tmp_path,check_local_files=False)
    assert not result["verified"] and result["status"]=="INCOMPLETE"
    assert any("forecast model unavailable" in warning for warning in result["warnings"])


def test_feasible_but_different_baseline_cannot_impersonate_declared_immediate(proof):
    e=copy.deepcopy(proof["evidence"])
    e["inputs"]["baseline_dispatch"]=copy.deepcopy(e["inputs"]["dispatch"])
    e["inputs"]["baseline_batch_starts"]=copy.deepcopy(e["inputs"]["batch_starts"])
    e["results"]["baseline_kgco2"]=e["results"]["plan_kgco2"]
    e["results"]["baseline_cost_gbp"]=e["results"]["cost_gbp"]
    e["results"]["difference_kgco2"]="0.000000000"
    for result in both(e,rehash(e)):
        assert result["levels"]["physical_validity"]["verified"]
        assert not result["verified"]
        assert any("baseline" in x for x in result["levels"]["source_lineage"]["errors"])


def test_legacy_v1_is_explicitly_degraded(proof):
    e=copy.deepcopy(proof["evidence"]);e["schema_version"]="1.0.0";e.pop("lineage")
    for result in both(e,rehash(e)):
        assert not result["verified"] and result["status"]=="INTEGRITY_ONLY"
        assert result["levels"]["integrity"]["verified"]
        assert result["levels"]["source_lineage"]["status"]=="LEGACY_UNVERIFIED"


def test_transform_config_and_forecast_issue_cannot_be_rewritten(proof):
    e=copy.deepcopy(proof["evidence"])
    e["lineage"]["configuration"]["transform_config"]["pv_outcome"]["performance_ratio"]="0.9"
    e["lineage"]["configuration_sha256"]=digest(e["lineage"]["configuration"])
    for result in both(e,rehash(e)):assert not result["verified"]
    e=copy.deepcopy(proof["evidence"])
    e["forecast_model"]["decision_time"]="2025-09-02T00:00:00Z"
    e["lineage"]["configuration"]["forecast_model"]=e["forecast_model"]
    e["lineage"]["configuration_sha256"]=digest(e["lineage"]["configuration"])
    for result in both(e,rehash(e)):
        assert not result["verified"]
        assert any("issue/latest" in x for x in result["errors"])


def test_legitimate_simulation_parameters_and_optional_external_config_commitment():
    run=compare(OptimizeRequest(date="2025-08-12",scenario=Scenario(solar_kwp=10,battery_capacity_kwh=20)))
    p=make_evidence(run["run_id"])
    assert verify_evidence(p["evidence"],p["digest"])["verified"]
    assert verify_evidence(p["evidence"],p["digest"],expected_config_digest="0"*64)["levels"]["source_lineage"]["status"]=="MISMATCH"


@pytest.mark.parametrize("policy",["peak_aware","peak_first"])
def test_peak_policy_uses_exact_scenario_and_separate_decision_solar(policy):
    p=make_evidence(compare(OptimizeRequest(date="2025-09-01"))["run_id"],policy)
    for result in both(p["evidence"],p["digest"]):assert result["verified"],result["errors"]
    if policy=="peak_aware":assert float(p["evidence"]["scenario_parameters"]["peak_weight"])==.2
    else:assert all(float(x["pv_forecast_kwh"])==0 for x in p["evidence"]["inputs"]["dispatch"])


def test_independent_cli_runs_without_backend_import_or_bulk(proof,tmp_path):
    script=tmp_path/"verify_evidence.py";shutil.copyfile(ROOT/"scripts/verify_evidence.py",script)
    trust=tmp_path/"data/trust";trust.mkdir(parents=True);shutil.copyfile(ROOT/"data/trust/source_anchors.v1.json",trust/"source_anchors.v1.json")
    path=tmp_path/"proof.json";path.write_text(json.dumps(proof),encoding="utf-8")
    result=subprocess.run([sys.executable,"-I",str(script),str(path),"--root",str(tmp_path)],capture_output=True,text=True,cwd=tmp_path)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)["levels"]["source_lineage"]["verified"]


def test_original_v2_base64_transport_remains_compatible(proof):
    e=copy.deepcopy(proof["evidence"])
    for blob in e["lineage"]["source_blobs"]+[e["lineage"]["model_blob"]]:
        raw=base64.b64decode(blob["body"],validate=True)
        if blob["encoding"]=="gzip+base64":raw=gzip.decompress(raw)
        blob["body"]=base64.b64encode(raw).decode("ascii")
        blob["encoding"]="base64"
    for result in both(e,rehash(e)):
        assert result["verified"] and result["status"]=="VERIFIED",result["errors"]


def test_producer_gzip_transport_has_portable_deterministic_header(proof):
    for blob in proof["evidence"]["lineage"]["source_blobs"]+[proof["evidence"]["lineage"]["model_blob"]]:
        assert blob["encoding"]=="gzip+base64"
        raw=base64.b64decode(blob["body"],validate=True)
        assert raw[:3]==b"\x1f\x8b\x08" and raw[4:8]==b"\x00"*4 and raw[9]==255


def test_real_compressed_overflow_is_bounded_and_rejected_by_both_verifiers(proof,monkeypatch):
    # A small transport expands beyond a deliberately small output cap.
    monkeypatch.setattr(independent_verifier,"MAX_SOURCE_BYTES",256)
    monkeypatch.setattr(independent_verifier,"MAX_ENCODED_BODY_CHARS",4096)
    e=copy.deepcopy(proof["evidence"])
    blob=e["lineage"]["source_blobs"][0]
    body=b'{"payload":"'+b"x"*512+b'"}'
    blob["body"]=base64.b64encode(gzip.compress(body,mtime=0)).decode("ascii")
    blob["encoding"]="gzip+base64"
    assert len(blob["body"])<256<len(body)
    for result in both(e,rehash(e)):
        assert not result["verified"] and result["status"]=="INVALID_EVIDENCE"
        assert result["levels"]["source_lineage"]["status"]=="MISMATCH"
        assert any("source snapshot exceeds supported transport size" in error for error in result["errors"])


def test_encoded_overflow_is_rejected_before_base64_decoder(proof,monkeypatch):
    monkeypatch.setattr(independent_verifier,"MAX_ENCODED_BODY_CHARS",64)
    def forbidden_decode(*args,**kwargs):
        pytest.fail("oversized encoded source must not reach base64 decoder")
    monkeypatch.setattr(independent_verifier.base64,"b64decode",forbidden_decode)
    e=copy.deepcopy(proof["evidence"])
    e["lineage"]["source_blobs"][0]["body"]="A"*68
    for result in both(e,rehash(e)):
        assert not result["verified"] and result["status"]=="INVALID_EVIDENCE"
        assert any("encoded source snapshot exceeds supported transport size" in error for error in result["errors"])


@pytest.mark.parametrize("corruption",["invalid_header","truncated","bad_crc"])
def test_corrupt_gzip_is_a_lineage_failure_not_an_exception(proof,corruption):
    raw=bytearray(gzip.compress(b'{"payload":"x"}',mtime=0))
    if corruption=="invalid_header":raw=bytearray(b"not gzip")
    elif corruption=="truncated":raw=raw[:-4]
    else:raw[-8]^=1
    e=copy.deepcopy(proof["evidence"])
    blob=e["lineage"]["source_blobs"][0]
    blob["body"]=base64.b64encode(raw).decode("ascii")
    blob["encoding"]="gzip+base64"
    for result in both(e,rehash(e)):
        assert not result["verified"] and result["status"]=="INVALID_EVIDENCE"
        assert result["levels"]["source_lineage"]["status"]=="MISMATCH"
        assert any("invalid compressed source transport" in error for error in result["errors"])


def test_local_original_snapshot_uses_same_bounded_read(tmp_path,monkeypatch):
    monkeypatch.setattr(independent_verifier,"MAX_SOURCE_BYTES",64)
    path=tmp_path/"source.json"
    path.write_bytes(b'{"payload":"'+b"x"*128+b'"}')
    def forbidden_read_bytes(*args,**kwargs):
        pytest.fail("local original source must not use an unbounded read")
    monkeypatch.setattr(Path,"read_bytes",forbidden_read_bytes)
    anchor={"source_id":"test-source","sha256":"0"*64,"paths":["source.json"]}
    with pytest.raises(ValueError,match="source snapshot exceeds supported transport size"):
        independent_verifier._load_pinned(None,anchor,tmp_path)
