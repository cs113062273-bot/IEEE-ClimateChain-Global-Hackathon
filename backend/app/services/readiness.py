"""Service-first, decision-time dispatch. Historical outcomes cannot select a plan.

This is an executable controller simulation, not a connected charger controller.
Full energy is promised by an operator-declared earliest departure. Events lock
executed controls and SoC; an infeasible event never replaces the previous plan.
"""
from __future__ import annotations
import copy
import math
import time
from typing import Literal
from pydantic import Field
from backend.app.domain.schemas import StrictModel, Scenario
from backend.app.domain.solver import solve, _result, _failure, TOL
from backend.app.domain.baselines import heuristic
from .data import prepare_intervals, envelope
from .evidence import digest
from . import storage


class ReadinessRequest(StrictModel):
    date: str = Field(default="2025-09-01", pattern=r"^2025-\d{2}-\d{2}$")
    protection_slots: int = Field(default=6, ge=1, le=24)
    scenario: Scenario = Field(default_factory=lambda: Scenario(peak_weight=.2))


class UpdateRequest(StrictModel):
    run_id: str
    at_slot: int = Field(ge=1, le=47)
    job_id: str
    energy_kwh: float = Field(gt=0, le=200)
    deadline_slot: int = Field(ge=1, le=48)


class DepartureRequest(StrictModel):
    run_id: str
    job_id: str
    at_slot: int = Field(ge=0, le=48)


def protect(scenario, slots):
    payload=scenario.model_dump()
    for job in payload["ev_jobs"]:
        job["deadline_slot"]=min(job["deadline_slot"],job["arrival_slot"]+slots)
    return Scenario.model_validate(payload)


def decision_view(inputs):
    # The legacy solver expects a finite actual column for arithmetic. In this
    # view that column is the prediction, never future observations.
    return [{**{k:v for k,v in x.items() if k not in (
        "solar_outcome_kwh","shortwave_radiation_w_per_m2","neso_historical_forecast_g_per_kwh")},
        "ci_actual_g_per_kwh":x["ci_forecast_g_per_kwh"],
        "pv_available_kwh":x["pv_forecast_kwh"]} for x in inputs]


def score_fixed(scenario, inputs, plan):
    """Score already fixed actions; never choose a fallback using an outcome."""
    if not plan or not plan.get("dispatch"): return plan
    records=copy.deepcopy(plan["dispatch"])
    planning=copy.deepcopy(plan["metrics"])
    for record,source in zip(records,inputs):
        record.update(source)
    scored=_result(scenario,records,plan["batch_starts"],plan["policy"],time.perf_counter(),
                   plan["solver"]["status"],plan["solver"].get("mip_gap"),plan["solver"]["message"])
    scored["solver"]=copy.deepcopy(plan["solver"])
    scored["planning_metrics"]={"emissions_kgco2":planning["emissions_kgco2"],
                                "cost_gbp":planning["cost_gbp"],"peak_grid_kw":planning["peak_grid_kw"]}
    scored["outcome_valid"]=scored["constraints"]["verified"]
    scored["outcome_policy"]="Fixed decisions; outcome scoring only; no retrospective fallback"
    scored["scenario_parameters"]=scenario.model_dump()
    return scored


def plan_service(scenario, inputs, *, prefix=None, starts=None, policy="hybrid"):
    decision=solve(scenario,decision_view(inputs),policy,.7,robust_import_cap=True,
                   frozen_prefix=prefix,frozen_starts=starts)
    if decision.get("dispatch") and decision["metrics"]["zero_pv_peak_envelope_kw"]>scenario.max_grid_import_kw+TOL:
        return _failure(policy,"No zero-PV-safe fallback available; change capacity or service request",time.perf_counter(),"unavailable")
    return score_fixed(scenario,inputs,decision)


def capacity_diagnostics(scenario, prefix=None, at_slot=0):
    """Necessary upper bounds, not a claim of jointly attainable capacity."""
    prefix=prefix or []
    jobs=[]
    for j,job in enumerate(scenario.ev_jobs):
        delivered=sum(x["ev_by_job_kwh"][j] for x in prefix)
        slots=max(0,job.deadline_slot-max(at_slot,job.arrival_slot))
        upper=delivered+slots*min(job.max_kw,scenario.charger_station_kw)*.5
        jobs.append({"id":job.id,"required_kwh":job.energy_kwh,"already_delivered_kwh":delivered,
                     "individual_upper_bound_kwh":upper,"unavoidable_shortfall_kwh":max(0,job.energy_kwh-upper),
                     "deadline_slot":job.deadline_slot})
    return {"jobs":jobs,"bound_scope":"Per-vehicle upper bound; shared grid, battery and charger constraints can reduce joint delivery further.",
            "next_action":"Extend the ready-by time, reduce requested energy, or provide another charger. The previous plan is not a promise for the changed request."}


def service_rows(scenario, plan):
    rows=[]
    for j,job in enumerate(scenario.ev_jobs):
        amounts=[x["ev_by_job_kwh"][j] for x in plan["dispatch"]]
        cumulative=[]; total=0
        for value in amounts:
            total+=value; cumulative.append(total)
        ready=next((t+1 for t,v in enumerate(cumulative) if v>=job.energy_kwh-TOL),None)
        rows.append({**job.model_dump(),"delivered_kwh":total,"ready_slot":ready,
                     "shortfall_kwh":max(0,job.energy_kwh-sum(amounts[:job.deadline_slot])),
                     "cumulative_kwh":[0]+cumulative})
    return rows


def _persist(date,scenario,inputs,model,plan,baseline,comparators,context,store):
    rows=service_rows(scenario,plan)
    value={"date":date,"scenario":scenario.model_dump(),"intervals":[{**x,"pv_available_kwh":x["solar_outcome_kwh"]} for x in inputs],
           "forecast_model":model,"carbon_weight":.7,"plans":{"peak_aware":plan,"immediate":baseline},
           "comparators":comparators,"service":rows,"operational_context":context,
           "status":"ready" if plan["constraints"]["verified"] else "outcome_invalid",**envelope(date)}
    # Include actual selected actions, not only request identity.
    value["run_id"]="service-"+digest({"scenario":value["scenario"],"inputs":inputs,
        "dispatch":plan["dispatch"],"context":context})[:20]
    if store: storage.put(value["run_id"],"run",value)
    return value


def create_readiness(request,store=True):
    scenario=protect(request.scenario,request.protection_slots)
    inputs,model=prepare_intervals(request.date,scenario)
    plan=plan_service(scenario,inputs)
    if not plan["dispatch"]:
        return {"status":"infeasible","diagnostics":capacity_diagnostics(scenario),"solver":plan["solver"],"scenario":scenario.model_dump()}
    baseline=plan_service(scenario,inputs,policy="immediate")
    comparators={"immediate":baseline}
    for key in ("greedy_cost","greedy_carbon","peak_heuristic"):
        candidate,error=heuristic(scenario,decision_view(inputs),key)
        comparators[key]=score_fixed(scenario,inputs,candidate) if candidate else {"dispatch":[],"metrics":None,"error":error}
    # Preserve the actual original policy for the explicitly unequal-service
    # diagnostic. It is never selected as this workflow's operational fallback.
    old=solve(request.scenario,inputs,"hybrid",.7)
    context={"schema":"gridproof-service-v1","mode":"historical_controller_simulation",
             "protection_slots":request.protection_slots,"at_slot":0,"events":[],
             "guarantee":"Full requested EV energy by each declared earliest departure, conditional on connection until then, declared demand/load, working chargers and battery; no unexpected outage guarantee.",
             "information_boundary":"Midnight past-only CI prediction, calendar PV, declared loads/tariff/requests. Outcome data is withheld from all decisions. No outcome-based fallback.",
             "original_scenario":request.scenario.model_dump()}
    result=_persist(request.date,scenario,inputs,model,plan,baseline,comparators,context,store)
    # Diagnostic only: this old plan did NOT promise the same early service.
    result["unprotected_reference"]={"metrics":old.get("metrics"),"service":service_rows(scenario,old) if old["dispatch"] else [],
                                       "comparison_scope":"Earlier readiness is an added service requirement; not an equal-service algorithm comparison."}
    return result


def update_readiness(request,store=True):
    parent=storage.get(request.run_id,"run")
    context=parent.get("operational_context")
    if not context: raise ValueError("Select a service plan before updating a request")
    if request.at_slot<=context["at_slot"]: raise ValueError("Events must move forward in simulated time")
    if request.deadline_slot<=request.at_slot: raise ValueError("Use departure assessment for a car leaving now; a replan deadline must be in the future")
    payload=copy.deepcopy(parent["scenario"])
    job=next((j for j in payload["ev_jobs"] if j["id"]==request.job_id),None)
    if job is None: raise ValueError("Unknown vehicle")
    job.update(energy_kwh=request.energy_kwh,deadline_slot=request.deadline_slot)
    scenario=Scenario.model_validate(payload)
    old=parent["plans"]["peak_aware"]
    prefix=old["dispatch"][:request.at_slot]
    inputs,model=prepare_intervals(parent["date"],scenario)
    plan=plan_service(scenario,inputs,prefix=prefix,starts=old["batch_starts"])
    if not plan["dispatch"]:
        diagnostics=capacity_diagnostics(scenario,prefix,request.at_slot)
        target=next(j for j in diagnostics["jobs"] if j["id"]==request.job_id)
        # Offer a separately solved deadline change; never silently relax the
        # user's service requirement. Bounded work even for adversarial inputs.
        remaining=max(0,request.energy_kwh-target["already_delivered_kwh"])
        lower=max(request.deadline_slot+1,request.at_slot+math.ceil(remaining/(min(job["max_kw"],scenario.charger_station_kw)*.5)-1e-8))
        diagnostics["recovery"]=None
        diagnostics["recovery_search"]="At most 6 later half-hour deadlines tested; no result is not a proof that all later deadlines are impossible."
        for deadline in range(lower,min(49,lower+6)):
            proposed=copy.deepcopy(payload)
            next(j for j in proposed["ev_jobs"] if j["id"]==request.job_id)["deadline_slot"]=deadline
            candidate=plan_service(Scenario.model_validate(proposed),inputs,prefix=prefix,starts=old["batch_starts"])
            if candidate.get("dispatch") and candidate["constraints"]["verified"]:
                diagnostics["recovery"]={"job_id":request.job_id,"deadline_slot":deadline,"energy_kwh":request.energy_kwh,
                                         "status":"feasible_proposal_requires_operator_acceptance","tested_deadlines_from":lower}
                break
        return {"status":"infeasible","previous_run_id":request.run_id,"diagnostics":diagnostics,"solver":plan["solver"],"scenario":scenario.model_dump()}
    # Day-start immediate is a retrospective equal-demand reference, not an
    # available action after the event. Excluded from event benefit claims.
    baseline=plan_service(scenario,inputs,policy="immediate")
    updated={**context,"at_slot":request.at_slot,"parent_run_id":request.run_id,
             "events":context["events"]+[{**request.model_dump(),"parent_dispatch_sha256":digest(old["dispatch"]),
                "parent_dispatch":old["dispatch"],"parent_batch_starts":old["batch_starts"],
                "parent_scenario":parent["scenario"]}],
             "comparison_scope":"Replan locks executed controls. Day-start baselines are not event-time alternatives; no event savings claim."}
    return _persist(parent["date"],scenario,inputs,model,plan,baseline,{},updated,store)


def departure_assessment(request):
    run=storage.get(request.run_id,"run")
    if request.at_slot<run["operational_context"]["at_slot"]: raise ValueError("Departure cannot precede the latest event")
    jobs=run["scenario"]["ev_jobs"]
    j=next((i for i,x in enumerate(jobs) if x["id"]==request.job_id),None)
    if j is None: raise ValueError("Unknown vehicle")
    job=jobs[j]
    delivered=sum(x["ev_by_job_kwh"][j] for x in run["plans"]["peak_aware"]["dispatch"][:request.at_slot])
    shortfall=max(0,job["energy_kwh"]-delivered)
    return {"run_id":request.run_id,"job_id":job["id"],"at_slot":request.at_slot,"required_kwh":job["energy_kwh"],
            "delivered_kwh":delivered,"unserved_kwh":shortfall,"status":"complete" if shortfall<TOL else "shortfall",
            "savings_claim_allowed":shortfall<TOL,"mode":"Simulated disconnect assessment; no vehicle command sent",
            "next_action":"Ready for departure." if shortfall<TOL else "Vehicle has left: re-optimization cannot recover missing energy. Arrange another charge or revise the trip; no savings claim for incomplete service."}
