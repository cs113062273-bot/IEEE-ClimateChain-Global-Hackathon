"""Judge-facing workflows preserve the source and chain trust boundaries."""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client=TestClient(app)

def test_trained_demo_and_peak_workload_comparison():
    assert "2025-09-01" in client.get("/api/scenarios").json()["available_dates"]
    r=client.post("/api/compare",json={"date":"2025-09-01"}).json()
    assert r["forecast_model"]["version"]=="lightgbm-past-only-v1"
    assert r["forecast_model"]["artifact_format"]=="portable-json"
    assert all(p["metrics"]["workload_kwh"]==pytest.approx(62) for p in r["plans"].values())
    assert r["plans"]["peak_aware"]["metrics"]["peak_grid_kw"]<r["plans"]["hybrid"]["metrics"]["peak_grid_kw"]
    assert r["forecast_accuracy"]["status"].startswith("retrospective")

def test_rehashed_forgery_is_rejected_by_api_and_original_hash():
    r=client.post("/api/compare",json={"date":"2025-09-01"}).json()
    proof=client.post("/api/evidence",json={"run_id":r["run_id"],"policy":"peak_aware"}).json()
    assert client.get("/api/evidence/"+proof["evidence_id"]).json()["digest"]==proof["digest"]
    v=client.post("/api/verify",json={"evidence":proof["evidence"],"expected_digest":proof["digest"]}).json()
    assert v["verified"] and not v["levels"]["onchain_attestation"]["verified"]
    attack=client.post("/api/attack-demo",json={"evidence_id":proof["evidence_id"]}).json()
    forged=attack["rehashed_verification"]
    assert not forged["verified"]
    assert forged["levels"]["integrity"]["verified"] and forged["levels"]["physical_validity"]["verified"]
    assert forged["levels"]["source_lineage"]["status"]=="MISMATCH"
    assert attack["original_commit_verification"]["status"]=="HASH_MISMATCH"

def test_public_service_disables_chain_writes_before_bridge(monkeypatch):
    monkeypatch.setenv("GRIDPROOF_ALLOW_CHAIN_WRITES","0")
    c=client.get("/api/chain-config").json()
    assert c["writes_enabled"] is False
    response=client.post("/api/attest",json={"evidence_id":"not-a-proof","network":"local"})
    assert response.status_code==403

def test_forecast_decision_view_does_not_return_outcome_accuracy():
    forecast=client.get("/api/forecast?from=2025-09-01T00:00:00Z").json()
    assert "forecast_accuracy" not in forecast
    assert all(x["ci_actual_g_per_kwh"] is None for x in forecast["intervals"])

@pytest.mark.parametrize("settings",[{"GRIDPROOF_READ_ONLY":"1"},{"GRIDPROOF_CHAIN_NETWORK":"testnet"}])
def test_service_guard_cannot_be_bypassed_with_local_request(monkeypatch,settings):
    for key,value in settings.items():monkeypatch.setenv(key,value)
    assert client.post("/api/attest",json={"evidence_id":"absent","network":"local"}).status_code==403

def test_duplicate_does_not_overwrite_existing_receipt(monkeypatch):
    from backend.app import main as api_module
    from backend.app.services import storage
    r=client.post("/api/compare",json={"date":"2025-09-01"}).json()
    proof=client.post("/api/evidence",json={"run_id":r["run_id"],"policy":"peak_aware"}).json()
    key="0x"+"a"*64
    original={"evidence_id":"old-evidence","receipt":{"status":"ATTESTED","transaction_hash":"old-transaction"}}
    storage.put("chain-"+key,"chain",original)
    monkeypatch.setattr(api_module,"call_bridge",lambda request:{"ok":False,"status":"REJECTED","claim_key":key,"error":{"code":"DUPLICATE_ACTIVE_CLAIM"}})
    response=client.post("/api/attest",json={"evidence_id":proof["evidence_id"],"network":"local"})
    assert response.json()["status"]=="REJECTED"
    assert storage.get("chain-"+key,"chain")==original
