"""Product service: replay a real held-out car-park day with live control decisions.

Everything returned is recomputed on request: the departure model's promises,
every half-hour decision, operator events and the outcome. The day itself is a
historical replay (real sessions, real grid records), never a live site.
"""
from __future__ import annotations
import copy
import json
from functools import lru_cache
from pathlib import Path
import numpy as np
from pydantic import Field, model_validator
from typing import Literal
from backend.app.domain.schemas import StrictModel
from backend.app.services import storage
from backend.app.services.evidence import digest
from .controller import Site, simulate, shortfall_bound, DT, T, SERVED_TOL_KWH, POLICIES
from .inputs import decision_cars, infeasible, possible_kwh, TRANSFORM
from .grid import grid_day
from .model import frozen, promises, model_fingerprint, history_counts
from .sessions import SOURCE, available, day_sessions, grid_date, site_days, load_sessions

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "experiments/carpark/test_results.json"
SUMMARY = ROOT / "experiments/carpark/test_summary.csv"
SELECTION = ROOT / "experiments/carpark/selection.json"
MODES = {"priority": "GridProof priority", "carbon_flex": "GridProof carbon-flex", "equal_share": "Equal-share load balancing"}


class CapEvent(StrictModel):
    type: Literal["cap"]
    at_slot: int = Field(ge=0, le=47)
    from_slot: int = Field(ge=0, le=47)
    to_slot: int = Field(ge=1, le=48)
    kw: float = Field(gt=0, le=1000)

    @model_validator(mode="after")
    def order(self):
        if not self.at_slot <= self.from_slot < self.to_slot:
            raise ValueError("A grid request must be issued before it starts and end after it starts")
        return self


class LeaveEvent(StrictModel):
    type: Literal["leave"]
    at_slot: int = Field(ge=0, le=47)
    car_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    departure_h: float = Field(ge=0, le=24)

    @model_validator(mode="after")
    def order(self):
        if self.departure_h < self.at_slot * DT:
            raise ValueError("A declared departure cannot be earlier than the moment it is declared")
        return self


class DayRequest(StrictModel):
    date: str = Field(pattern=r"^20\d{2}-\d{2}-\d{2}$")
    connection_kw: float = Field(default=120, ge=60, le=400)
    mode: Literal["priority", "carbon_flex", "equal_share"] = "priority"
    events: list[CapEvent | LeaveEvent] = Field(default_factory=list, max_length=12)


@lru_cache(maxsize=1)
def selection():
    if not SELECTION.exists():
        raise ValueError("Run scripts/evaluate_carpark.py --stage validate to freeze the controller selection")
    return json.loads(SELECTION.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def replay_days():
    """Held-out 2024 days only: these were never used to select the method."""
    return tuple(site_days("test"))


@lru_cache(maxsize=1)
def day_counts():
    return {d: len(day_sessions(d)) for d in replay_days()}


def default_day():
    """Declared rule: the earliest held-out day whose session count equals the period median."""
    days = replay_days()
    counts = day_counts()
    median = int(np.median(list(counts.values())))
    return next(d for d in days if counts[d] == median)


def _cars(sessions, mode):
    sp, flex = selection()["service_policy"], selection()["carbon_flex"]
    promise, risks, quantiles = promises(sessions, "lightgbm", sp["level"])
    if mode == "carbon_flex":
        hard = flex["hard_promise_level"]
        hard_promise = promises(sessions, "lightgbm", hard)[0] if hard is not None else np.full(len(sessions), 24.0)
        cars = decision_cars(sessions, hard_promise, risks=risks)
    else:
        cars = decision_cars(sessions, promise)
    # Hindsight count for reporting only: requests no schedule could meet at 11 kW before the real departure.
    return cars, sum(infeasible(c) for c in cars), dict(zip(sessions.session_id, quantiles.tolist()))


def _policy(mode):
    return {"priority": selection()["service_policy"]["policy"], "carbon_flex": "optimised", "equal_share": "equal_share"}[mode]


def _site(mode, kw):
    site = Site(connection_kw=kw)
    return site if mode != "carbon_flex" else Site(connection_kw=kw, risk_penalty=selection()["carbon_flex"]["risk_penalty"])


def _events(request, cars):
    ids = {c.id for c in cars}
    out = []
    for e in sorted(request.events, key=lambda e: e.at_slot):
        value = e.model_dump()
        if e.type == "leave":
            car = next((c for c in cars if c.id == e.car_id), None)
            if car is None or car.id not in ids:
                raise ValueError("Unknown car for the declared departure")
            if not (car.arrival_h <= e.at_slot * DT < car.departure_h):
                raise ValueError("A driver can only declare a departure while plugged in")
        out.append(value)
    return out


def metrics(result):
    keys = ["sessions", "served", "requested_kwh", "delivered_kwh", "unserved_kwh", "max_unserved_kwh", "emissions_kgco2",
            "cost_gbp", "peak_import_kw", "peak_envelope_kw", "cap_exceeded_slots", "solves", "solve_seconds"]
    return {k: result[k] for k in keys}


def run_day(request, store=True):
    if not available():
        raise ValueError("Workplace session data not downloaded. Run scripts/fetch_workplace_sessions.py (public, no account).")
    if request.date not in replay_days():
        raise ValueError("Choose one of the held-out 2024 replay days")
    sessions = day_sessions(request.date)
    gdate = grid_date(request.date)
    grid = grid_day(gdate)
    cars, impossible, quantiles = _cars(sessions, request.mode)
    events = _events(request, cars)
    policy = _policy(request.mode)
    result = simulate(cars, grid, _site(request.mode, request.connection_kw), policy, events=events, record=True)
    # Same day, same events, other policies: what the operator would otherwise get.
    compare = {}
    for mode in ("equal_share", "priority", "carbon_flex"):
        if mode == request.mode:
            continue
        other, _, _ = _cars(sessions, mode)
        compare[mode] = metrics(simulate(other, grid, _site(mode, request.connection_kw), _policy(mode), events=_events(request, other)))
    uncontrolled = simulate(cars, grid, Site(connection_kw=10_000), "uncontrolled", events=events, record=True)
    levels = list(frozen()[0]["lightgbm"].levels)
    effective = {c.id: c for c in result["cars"]}
    history = history_counts()
    rows = []
    for k, car in enumerate(cars):  # original decision inputs; simulate() worked on a copy
        now = effective[car.id]
        rows.append({"id": car.id, "driver": car.driver, "arrival_h": car.arrival_h, "request_kwh": car.request_kwh,
                     "max_kw": car.max_kw, "promise_h": car.promise_h,
                     "possible_kwh": float(possible_kwh(car)), "infeasible": bool(infeasible(car)),
                     "risk": [list(p) for p in car.risk],
                     "departure_quantiles_h": {f"{l:.2f}": float(car.arrival_h + q) for l, q in zip(levels, quantiles[car.id])},
                     "history_sessions": history[car.id],
                     "departure_h": car.departure_h, "effective_departure_h": now.departure_h, "effective_promise_h": now.promise_h,
                     "declared": now.departure_h != car.departure_h or now.promise_h != car.promise_h,
                     "delivered_kwh": float(result["delivered"][k]), "unserved_kwh": float(result["unserved"][k]),
                     "served": bool(result["unserved"][k] <= SERVED_TOL_KWH),
                     "executed_kwh": [float(x) for x in result["executed"][k]]})
    slots = []
    for t in range(T):
        slots.append({"slot": t, "start_utc": grid["start_utc"][t], "cap_kw": float(result["cap_kw"][t]),
                      "base_kw": float(grid["base_load"][t] / DT), "ev_kw": float(result["executed"][:, t].sum() / DT),
                      "envelope_kw": float(result["envelope"][t] / DT), "import_kw": float(result["imports"][t] / DT),
                      "pv_forecast_kw": float(grid["pv_forecast"][t] / DT), "pv_outcome_kw": float(grid["pv_outcome"][t] / DT),
                      "ci_forecast": float(grid["ci_forecast"][t]), "ci_actual": float(grid["ci_actual"][t]),
                      "tariff": float(grid["tariff"][t]), "uncontrolled_kw": float(uncontrolled["envelope"][t] / DT),
                      **result["trace"][t]})
    value = {
        "kind": "carpark-day", "schema": "gridproof-carpark-v1",
        "date": request.date, "grid_date": gdate, "mode": request.mode, "mode_label": MODES[request.mode],
        "policy": policy, "policy_description": POLICIES[policy], "connection_kw": request.connection_kw,
        "events": events, "cars": rows, "slots": slots, "metrics": metrics(result), "compare": compare,
        "uncontrolled": {"peak_envelope_kw": uncontrolled["peak_envelope_kw"],
                         "slots_over_connection": int((uncontrolled["envelope"] > result["cap_kw"] * DT + 1e-6).sum())},
        "impossible_requests": impossible, "input_transform": TRANSFORM,
        "information_boundary": "Decisions at each half-hour use only cars plugged in by then, the energy they declared at plug-in, the charger's fixed 11 kW limit and departure-risk quantiles from earlier sessions, whether they are still connected, the past-only carbon forecast and calendar PV. True departures, future arrivals and actual carbon/PV enter only after each slot is executed.",
        "evidence_level": "Historical replay: real 2024 workplace sessions (Utrecht, NL) on a same-weekday 2025 GB grid day. Synthetic campus base load and tariff. Simulated chargers; no hardware commands.",
        "model": {"version": frozen()[3]["version"], "fingerprint": model_fingerprint(), "selection": selection()["service_policy"],
                  "carbon_flex": selection()["carbon_flex"]},
        "source": SOURCE, "grid_sources_sha256": grid["source_sha256"],
    }
    value["run_id"] = "carpark-" + digest({"request": request.model_dump(), "cars": rows, "slots": slots})[:20]
    if store:
        storage.put(value["run_id"], "carpark", value)
    return value
