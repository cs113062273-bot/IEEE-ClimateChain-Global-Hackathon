"""Online car-park charging under a connection cap, replayed on real sessions.

Information boundary (enforced by construction, tested):
  * At slot t the controller sees only cars that plugged in at or before the slot
    start: their arrival, requested energy, power limit and departure-risk promise,
    plus whether each is still connected. True departure times and future arrivals
    exist only in the simulator.
  * Decisions use the past-only carbon forecast and calendar PV. Actual carbon and
    radiation-derived PV are applied after the slot is executed.
  * Executed energy is never rewritten: each solve covers slots t..47 only.

Capacity guard: base load + EV charging <= connection cap with ZERO solar, in
every slot, for every policy that claims cap compliance.
"""
from __future__ import annotations
import copy
import math
import time
from dataclasses import dataclass, field, asdict
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

T = 48
DT = .5
TOL = 1e-6
SERVED_TOL_KWH = .05


@dataclass(frozen=True)
class Site:
    connection_kw: float = 150.0
    charger_kw: float = 11.0
    solar_kwp: float = 20.0
    carbon_weight: float = .7
    peak_weight: float = .2
    peak_reference_kw: float = 60.0
    shortfall_penalty: float = 1.0       # per kWh unmet by the hard promise; dominates energy terms
    risk_penalty: float = 0.03           # per kWh of expected unserved energy under the departure distribution
    early_preference: float = 1e-6       # tie-break toward earlier delivery (hedge)


@dataclass
class Car:
    id: str
    driver: str
    arrival_h: float
    request_kwh: float
    max_kw: float
    promise_h: float                     # decision-time: hard deliver-by hour (UTC)
    risk: tuple = ()                     # decision-time: ((hour, probability), ...) departure distribution
    departure_h: float = field(default=math.nan, repr=False)  # simulator only

    @property
    def first_slot(self):
        return int(math.ceil(self.arrival_h / DT - 1e-9))

    def public(self):
        value = asdict(self); value.pop("departure_h"); return value


def present_fraction(car, t):
    """1 if the car is connected for all of slot t (simulator truth), else 0.

    Partial first/last half-hours are not used by any policy, so every request
    clipped to the as-soon-as-possible amount is exactly servable.
    """
    return 1.0 if car.first_slot <= t and car.departure_h >= (t + 1) * DT - 1e-9 else 0.0


def deliverable_kwh(car, request=None):
    """Energy an as-soon-as-possible schedule delivers under the slot execution model."""
    remaining = car.request_kwh if request is None else request; total = 0.0
    for t in range(car.first_slot, T):
        got = min(car.max_kw * DT, remaining) * present_fraction(car, t)
        total += got; remaining -= got
        if remaining <= TOL:
            break
    return total


def deadline_slot(car, t):
    return min(T, max(t + 1, int(math.floor(car.promise_h / DT + 1e-9))))


def conditional_risk(car, t):
    """Departure points after slot start t, renormalised: the car is known to be present."""
    points = [(h, w) for h, w in car.risk if h > t * DT + 1e-9]
    total = sum(w for _, w in points)
    return [(h, w / total) for h, w in points] if total > 0 else []


def solve_remaining(t, cars, remaining, grid, site, cap_kw=None, past_peak_kw=0.0):
    """LP over slots t..47 for connected cars. Returns plan (n, 48-t) in kWh.

    Hard promise: energy by the promise slot, with a dominant penalty on any gap.
    Risk term: expected unserved energy if the driver leaves at each calibrated
    departure point, weighted by its conditional probability.
    """
    n, H = len(cars), T - t
    if n == 0:
        return np.zeros((0, H)), {"status": "idle", "seconds": 0.0}
    started = time.perf_counter()
    cap = np.asarray(cap_kw if cap_kw is not None else np.full(T, site.connection_kw), dtype=float)
    base = grid["base_load"][t:]; pv = grid["pv_forecast"][t:]
    headroom = cap[t:] * DT - base
    if np.any(headroom < -TOL):
        raise ValueError("Connection cap below building base load")
    risks = [conditional_risk(car, t) for car in cars]
    nS = sum(len(r) for r in risks)
    nP = n * H; iU = nP; iI = iU + n; iZ = iI + H; iS = iZ + 1; nv = iS + nS
    ub = np.zeros(nv); lb = np.zeros(nv)
    for i, car in enumerate(cars):
        start = max(t, car.first_slot)
        ub[i * H + (start - t):(i + 1) * H] = car.max_kw * DT
    ub[iU:iU + n] = remaining; ub[iI:iI + H] = np.inf; ub[iZ] = np.inf
    lb[iZ] = past_peak_kw
    ub[iS:iS + nS] = np.inf
    rows, cols, vals, rhs = [], [], [], []
    r = 0
    hs = np.arange(H)
    for h in range(H):  # cap with zero PV; import epigraph; peak envelope
        idx = np.arange(n) * H + h
        rows += [r] * n; cols += list(idx); vals += [1.0] * n; rhs.append(headroom[h]); r += 1
        rows += [r] * (n + 1); cols += list(idx) + [iI + h]; vals += [1.0] * n + [-1.0]; rhs.append(pv[h] - base[h]); r += 1
        rows += [r] * (n + 1); cols += list(idx) + [iZ]; vals += [1.0] * n + [-DT]; rhs.append(-base[h]); r += 1
    for i, car in enumerate(cars):
        d = deadline_slot(car, t) - t
        idx = i * H + np.arange(d)
        rows += [r] * (d + 1); cols += list(idx) + [iU + i]; vals += [-1.0] * d + [-1.0]; rhs.append(-remaining[i]); r += 1
        idx = i * H + hs
        rows += [r] * H; cols += list(idx); vals += [1.0] * H; rhs.append(remaining[i]); r += 1
    k = iS; weights = []
    for i, points in enumerate(risks):
        for hour, weight in points:  # s_ik >= R_i - energy delivered before that departure
            e = min(H, max(0, int(math.floor(hour / DT + 1e-9)) - t))
            idx = i * H + np.arange(e)
            rows += [r] * (e + 1); cols += list(idx) + [k]; vals += [-1.0] * e + [-1.0]; rhs.append(-remaining[i]); r += 1
            weights.append(weight); k += 1
    A = coo_matrix((vals, (rows, cols)), shape=(r, nv)).tocsr()
    unit = site.carbon_weight * grid["ci_forecast"][t:] / 1000 / 50 + (1 - site.carbon_weight) * grid["tariff"][t:] / 100
    c = np.zeros(nv)
    c[:nP] = np.tile(site.early_preference * hs, n)
    c[iU:iU + n] = site.shortfall_penalty
    c[iI:iI + H] = unit
    c[iZ] = site.peak_weight / site.peak_reference_kw
    c[iS:iS + nS] = site.risk_penalty * np.array(weights)
    result = linprog(c, A_ub=A, b_ub=np.array(rhs), bounds=np.column_stack([lb, ub]), method="highs")
    if result.status != 0:
        raise RuntimeError(f"Charging LP failed at slot {t}: {result.message}")
    plan = np.maximum(result.x[:nP].reshape(n, H), 0)
    return plan, {"status": "optimal", "seconds": time.perf_counter() - started,
                  "promised_shortfall_kwh": float(result.x[iU:iU + n].sum()),
                  "expected_unserved_kwh": float(np.dot(weights, result.x[iS:iS + nS])) if nS else 0.0}


def equal_share(t, cars, remaining, grid, site, cap_kw=None):
    """Industry-default dynamic load balancing: split headroom equally, no departure info."""
    cap = cap_kw[t] if cap_kw is not None else site.connection_kw
    room = cap * DT - grid["base_load"][t]
    limit = np.array([min(c.max_kw * DT, r) for c, r in zip(cars, remaining)])
    out = np.zeros(len(cars)); open_ = limit > TOL
    while room > TOL and open_.any():
        share = room / open_.sum()
        take = np.where(open_, np.minimum(share, limit - out), 0)
        out += take; room -= take.sum(); open_ &= out < limit - TOL
    return out


def earliest_deadline(t, cars, remaining, grid, site, cap_kw=None):
    """Deadline-ordered greedy (EDF) using the same promise; no carbon/cost objective."""
    cap = cap_kw[t] if cap_kw is not None else site.connection_kw
    room = cap * DT - grid["base_load"][t]
    out = np.zeros(len(cars))
    for i in sorted(range(len(cars)), key=lambda i: (deadline_slot(cars[i], t), -remaining[i], cars[i].id)):
        take = max(0.0, min(cars[i].max_kw * DT, remaining[i], room)); out[i] = take; room -= take
    return out


def least_laxity(t, cars, remaining, grid, site, cap_kw=None):
    """Least-laxity-first: slack = slots left before the promise minus slots of charging still needed."""
    cap = cap_kw[t] if cap_kw is not None else site.connection_kw
    room = cap * DT - grid["base_load"][t]
    out = np.zeros(len(cars))
    laxity = [deadline_slot(c, t) - t - r / (c.max_kw * DT) for c, r in zip(cars, remaining)]
    for i in sorted(range(len(cars)), key=lambda i: (laxity[i], cars[i].id)):
        take = max(0.0, min(cars[i].max_kw * DT, remaining[i], room)); out[i] = take; room -= take
    return out


POLICIES = {
    "uncontrolled": "Each car at full power from plug-in; no connection limit (reference only)",
    "equal_share": "Dynamic load balancing: equal split of headroom, ASAP, no departure or carbon information",
    "edf": "Earliest-promise-first greedy under the cap; no carbon/cost objective",
    "llf": "Least-laxity-first greedy under the cap using the same promise; no carbon/cost objective",
    "optimised": "GridProof LP: carbon/cost/peak objective, promise-constrained, replanned each slot",
}


def shortfall_bound(t, cars, remaining, grid, cap_kw):
    """Minimum total gap to the promises of the connected cars, over all schedules.

    An LP over slots t..47 with only the cap, power limits and promise deadlines.
    Future arrivals can only make it worse, so this is a lower bound on the
    unavoidable shortfall. Returns per-car kWh.
    """
    if not cars:
        return []
    site = Site(carbon_weight=0, peak_weight=0, early_preference=0, risk_penalty=0)
    flat = dict(grid, ci_forecast=np.zeros(T), tariff=np.zeros(T))
    plan, _ = solve_remaining(t, [Car(c.id, c.driver, c.arrival_h, c.request_kwh, c.max_kw, c.promise_h) for c in cars],
                              remaining, flat, site, cap_kw)
    return [float(max(0.0, r - plan[i, :deadline_slot(c, t) - t].sum())) for i, (c, r) in enumerate(zip(cars, remaining))]


def apply_event(event, cars, cap, t):
    """Operator changes known from slot t; executed energy is never touched."""
    if event["type"] == "cap":
        cap[event["from_slot"]:event["to_slot"]] = event["kw"]
    elif event["type"] == "leave":
        car = next(c for c in cars if c.id == event["car_id"])
        # What-if: the driver leaves at the declared time, and the controller knows it from now.
        car.departure_h = event["departure_h"]
        car.promise_h = event["departure_h"]
        car.risk = ((event["departure_h"], 1.0),)
    else:
        raise ValueError(f"Unknown event type {event['type']}")


def simulate(cars, grid, site, policy="optimised", cap_kw=None, events=None, record=False):
    """Replay one day. `events`: [{type, at_slot, ...}] applied at the start of their slot."""
    cars = copy.deepcopy(cars)
    for car in cars:
        if not math.isfinite(car.departure_h):
            raise ValueError("Simulator requires true departure times")
    n = len(cars)
    delivered = np.zeros(n); executed = np.zeros((n, T)); envelope = np.zeros(T)
    cap = np.array(cap_kw if cap_kw is not None else np.full(T, site.connection_kw), dtype=float)
    pending = sorted(events or [], key=lambda e: e["at_slot"])
    plan = None; key = None; solves = 0; solve_seconds = 0.0; decisions = []; trace = []
    for t in range(T):
        while pending and pending[0]["at_slot"] == t:
            apply_event(pending.pop(0), cars, cap, t); plan = None
        start = t * DT
        visible = [i for i, c in enumerate(cars) if c.arrival_h <= start + 1e-9 and c.departure_h > start]
        active = [i for i in visible if cars[i].request_kwh - delivered[i] > TOL]
        remaining = np.array([cars[i].request_kwh - delivered[i] for i in active])
        allocation = np.zeros(len(active))
        if active:
            if policy == "uncontrolled":
                allocation = np.array([min(cars[i].max_kw * DT, remaining[k]) for k, i in enumerate(active)])
            elif policy == "equal_share":
                allocation = equal_share(t, [cars[i] for i in active], remaining, grid, site, cap)
            elif policy == "edf":
                allocation = earliest_deadline(t, [cars[i] for i in active], remaining, grid, site, cap)
            elif policy == "llf":
                allocation = least_laxity(t, [cars[i] for i in active], remaining, grid, site, cap)
            elif policy == "optimised":
                state = (tuple(active), tuple(deadline_slot(cars[i], t) for i in active), tuple(cap[t:]),
                         tuple(len(conditional_risk(cars[i], t)) for i in active))
                if plan is None or state[0] != key[0] or state[1] != key[1] or state[2] != key[2]:
                    past_peak = envelope[:t].max() / DT if t else 0.0
                    plan, info = solve_remaining(t, [cars[i] for i in active], remaining, grid, site, cap, past_peak)
                    key = state; plan_t0 = t; solves += 1; solve_seconds += info["seconds"]
                    if record:
                        decisions.append({"slot": t, "connected": [cars[i].id for i in active],
                                          "remaining_kwh": [float(x) for x in remaining],
                                          "deadline_slots": [deadline_slot(cars[i], t) for i in active],
                                          "promised_shortfall_kwh": info["promised_shortfall_kwh"],
                                          "expected_unserved_kwh": info["expected_unserved_kwh"]})
                allocation = np.minimum(plan[:, t - plan_t0], remaining)
            else:
                raise ValueError(f"Unknown policy {policy}")
        if record:
            order = sorted(range(len(active)), key=lambda k: (deadline_slot(cars[active[k]], t), -remaining[k], cars[active[k]].id))
            bound = shortfall_bound(t, [cars[i] for i in active], remaining, grid, cap) if active and policy != "uncontrolled" else []
            trace.append({"visible": [cars[i].id for i in visible], "active": [cars[i].id for i in active],
                          "remaining_kwh": [float(x) for x in remaining], "allocated_kwh": [float(x) for x in allocation],
                          "deadline_slots": [deadline_slot(cars[i], t) for i in active],
                          "priority": [cars[active[k]].id for k in order],
                          "promise_gap_bound_kwh": bound})
        for k, i in enumerate(active):
            got = allocation[k] * present_fraction(cars[i], t)
            executed[i, t] = got; delivered[i] += got
        envelope[t] = grid["base_load"][t] + executed[:, t].sum()
    imports = np.maximum(0, envelope - grid["pv_outcome"])
    unserved = np.array([max(0.0, c.request_kwh - d) for c, d in zip(cars, delivered)])
    result = {
        "policy": policy, "sessions": n, "served": int((unserved <= SERVED_TOL_KWH).sum()),
        "requested_kwh": float(sum(c.request_kwh for c in cars)), "delivered_kwh": float(delivered.sum()),
        "unserved_kwh": float(unserved.sum()), "max_unserved_kwh": float(unserved.max()) if n else 0.0,
        "emissions_kgco2": float((imports * grid["ci_actual"]).sum() / 1000),
        "cost_gbp": float((imports * grid["tariff"]).sum()),
        "peak_import_kw": float(imports.max() / DT), "peak_envelope_kw": float(envelope.max() / DT),
        "cap_exceeded_slots": int((envelope > cap * DT + 1e-6).sum()),
        "solves": solves, "solve_seconds": solve_seconds,
    }
    if record:
        result.update(executed=executed, delivered=delivered, unserved=unserved, envelope=envelope,
                      imports=imports, decisions=decisions, cap_kw=cap, trace=trace, cars=cars)
    return result
