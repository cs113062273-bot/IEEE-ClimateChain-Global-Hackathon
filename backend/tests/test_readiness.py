import copy
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.domain.schemas import Scenario
from backend.app.services.data import prepare_intervals
from backend.app.services.readiness import (ReadinessRequest,UpdateRequest,DepartureRequest,
    create_readiness,update_readiness,departure_assessment,plan_service,protect)
from backend.app.services.evidence import make_evidence,verify_evidence,digest
from scripts.verify_evidence import inspect,verify_service_context
from pathlib import Path


def test_early_service_and_equal_equipment_baselines():
    run=create_readiness(ReadinessRequest())
    assert run['status']=='ready'
    assert all(j['shortfall_kwh']<1e-5 for j in run['service'])
    assert sum(j['shortfall_kwh'] for j in run['unprotected_reference']['service'])>20
    for p in run['comparators'].values():
        assert p['constraints']['verified']
        assert p['metrics']['workload_kwh']==62
        assert p['dispatch'][-1]['soc_end_kwh']==pytest.approx(20)


def test_outcomes_cannot_change_decision_or_choose_fallback():
    s=protect(Scenario(peak_weight=.2),6)
    inputs=prepare_intervals('2025-09-01',s)[0]
    extreme=copy.deepcopy(inputs)
    for x in extreme:
        x.update(ci_actual_g_per_kwh=1400,solar_outcome_kwh=0,shortwave_radiation_w_per_m2=0)
    a,b=plan_service(s,inputs),plan_service(s,extreme)
    assert b['constraints']['verified']
    assert a['solver']['status']==b['solver']['status']
    for x,y in zip(a['dispatch'],b['dispatch']):
        for key in ['ev_by_job_kwh','battery_charge_kwh','battery_discharge_kwh','batch_load_kwh']:
            assert x[key]==pytest.approx(y[key])


def test_update_preserves_actions_soc_and_independent_evidence():
    parent=create_readiness(ReadinessRequest())
    run=update_readiness(UpdateRequest(run_id=parent['run_id'],at_slot=17,job_id='fleet-a',energy_kwh=28,deadline_slot=22))
    assert run['status']=='ready'
    for x,y in zip(parent['plans']['peak_aware']['dispatch'][:17],run['plans']['peak_aware']['dispatch'][:17]):
        for key in ['ev_by_job_kwh','battery_charge_kwh','battery_discharge_kwh','soc_end_kwh','batch_load_kwh']:
            assert x[key]==pytest.approx(y[key])
    proof=make_evidence(run['run_id'],'peak_aware')
    assert verify_evidence(proof['evidence'],proof['digest'])['verified']
    result=inspect(proof['evidence'],proof['digest'],Path(__file__).resolve().parents[2],check_local_files=False)
    assert result['verified'],result['errors']
    forged=copy.deepcopy(proof['evidence'])
    event=forged['operational_context']['events'][0]
    event['parent_dispatch'][14]['ev_by_job_kwh'][0]='0.000000000'
    event['parent_dispatch_sha256']=digest(event['parent_dispatch'])
    assert 'executed prefix' in verify_service_context(forged)[0]


def test_infeasible_update_does_not_overwrite_and_disconnect_is_shortfall():
    parent=create_readiness(ReadinessRequest())
    result=update_readiness(UpdateRequest(run_id=parent['run_id'],at_slot=17,job_id='fleet-a',energy_kwh=100,deadline_slot=18))
    assert result['status']=='infeasible'
    assert result['diagnostics']['jobs'][0]['unavoidable_shortfall_kwh']>70
    assert 'run_id' not in result
    recovery=result['diagnostics']['recovery']
    assert recovery and recovery['deadline_slot']>18
    accepted=update_readiness(UpdateRequest(run_id=parent['run_id'],at_slot=17,job_id='fleet-a',energy_kwh=100,deadline_slot=recovery['deadline_slot']))
    assert accepted['status']=='ready'
    assert accepted['service'][0]['shortfall_kwh']<1e-5
    departure=departure_assessment(DepartureRequest(run_id=parent['run_id'],job_id='fleet-a',at_slot=16))
    assert departure['unserved_kwh']==pytest.approx(13)
    assert not departure['savings_claim_allowed']
    assert departure_assessment(DepartureRequest(run_id=parent['run_id'],job_id='fleet-a',at_slot=20))['status']=='complete'


def test_api_physical_impossibility_missing_data_and_event_order():
    client=TestClient(app)
    blocked=client.post('/api/service/plan',json={'protection_slots':4})
    assert blocked.status_code==200
    assert blocked.json()['status']=='infeasible'
    assert blocked.json()['diagnostics']['jobs'][0]['unavoidable_shortfall_kwh']==2
    assert client.post('/api/service/plan',json={'date':'2025-09-02'}).status_code==422
    run=create_readiness(ReadinessRequest())
    event=UpdateRequest(run_id=run['run_id'],at_slot=17,job_id='fleet-a',energy_kwh=28,deadline_slot=22)
    updated=update_readiness(event)
    with pytest.raises(ValueError,match='forward'):
        update_readiness(event.model_copy(update={'run_id':updated['run_id']}))
