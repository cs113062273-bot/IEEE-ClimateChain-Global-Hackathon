"""Sensitivity of the FROZEN car-park policies to key assumptions (2024 test days).

  .venv/Scripts/python.exe scripts/sensitivity_carpark.py

Nothing is re-selected: policy, model and promise level come from selection.json.
Each case changes one assumption for every policy alike.
  nominal              as evaluated
  slow_cars_7kw        every car limited to 7.4 kW (single-phase); requests re-clipped
  building_load_x2     synthetic building load doubled
  requests_unknown     controller ranks with each driver's median past request (first-timers 20 kWh);
                       cars still stop drawing only when actually full
  decision_delay_30min each car becomes visible one slot later than it plugged in
"""
from __future__ import annotations
import copy
import json
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.fleet.controller import Site, simulate, deliverable_kwh, DT, SERVED_TOL_KWH
from backend.app.fleet.day import make_cars
from backend.app.fleet.grid import grid_day
from backend.app.fleet.model import frozen, promises
from backend.app.fleet.sessions import day_sessions, grid_date, site_days

OUT = ROOT / "experiments/carpark"
CAPS = (100, 120, 150)


def typical_requests(df):
    """Median request per driver from sessions on strictly earlier dates."""
    out, history = {}, {}
    for date, group in df.sort_values("start_utc").groupby("date", sort=True):
        for sid, driver in zip(group.session_id, group.driver):
            past = history.get(driver) if driver != "shared" else None
            out[sid] = float(np.median(past)) if past else 20.0
        for driver, energy in zip(group.driver, group.energy_kwh):
            if driver != "shared":
                history.setdefault(driver, []).append(energy)
    return out


def run_case(case, cars, grid, cap, policy, typical=None):
    cars = copy.deepcopy(cars); g = dict(grid); site = Site(connection_kw=cap)
    if case == "slow_cars_7kw":
        for c in cars:
            c.max_kw = 7.4; c.request_kwh = min(c.request_kwh, deliverable_kwh(c, request=c.request_kwh))
    elif case == "building_load_x2":
        g["base_load"] = grid["base_load"] * 2
    elif case == "decision_delay_30min":
        for c in cars:
            c.arrival_h += DT
            c.request_kwh = min(c.request_kwh, deliverable_kwh(c))
    if case == "requests_unknown":
        return unknown_requests(cars, g, site, policy, typical)
    result = simulate(cars, g, site, policy)
    return {k: result[k] for k in ("served", "unserved_kwh", "requested_kwh", "sessions", "emissions_kgco2", "cap_exceeded_slots")}


def unknown_requests(cars, grid, site, policy, typical):
    """The controller ranks by the driver's typical request; each car still stops when actually full.

    Equal share never uses the request (cars stop drawing when full), so it is unchanged.
    For earliest-promise-first the request only breaks ties between equal deadlines.
    """
    from backend.app.fleet.controller import T, TOL, present_fraction, deadline_slot, equal_share
    n = len(cars); delivered = np.zeros(n); envelope = np.zeros(T)
    for t in range(T):
        start = t * DT
        active = [i for i, c in enumerate(cars) if c.arrival_h <= start + 1e-9 and c.departure_h > start and c.request_kwh - delivered[i] > TOL]
        truth = np.array([cars[i].request_kwh - delivered[i] for i in active])
        if active and policy == "equal_share":
            alloc = equal_share(t, [cars[i] for i in active], truth, grid, site)
        elif active:
            believed = [max(0.0, typical[cars[i].id] - delivered[i]) for i in active]
            room = site.connection_kw * DT - grid["base_load"][t]; alloc = np.zeros(len(active))
            for k in sorted(range(len(active)), key=lambda k: (deadline_slot(cars[active[k]], t), -believed[k], cars[active[k]].id)):
                take = max(0.0, min(cars[active[k]].max_kw * DT, truth[k], room)); alloc[k] = take; room -= take
        else:
            alloc = []
        for k, i in enumerate(active):
            got = alloc[k] * present_fraction(cars[i], t); delivered[i] += got; envelope[t] += got
        envelope[t] += grid["base_load"][t]
    unserved = np.array([max(0.0, c.request_kwh - d) for c, d in zip(cars, delivered)])
    imports = np.maximum(0, envelope - grid["pv_outcome"])
    return {"served": int((unserved <= SERVED_TOL_KWH).sum()), "unserved_kwh": float(unserved.sum()),
            "requested_kwh": float(sum(c.request_kwh for c in cars)), "sessions": n,
            "emissions_kgco2": float((imports * grid["ci_actual"]).sum() / 1000),
            "cap_exceeded_slots": int((envelope > site.connection_kw * DT + 1e-6).sum())}


def main():
    selection = json.loads((OUT / "selection.json").read_text())
    level = selection["service_policy"]["level"]
    _, _, df, _ = frozen()
    typical = typical_requests(df)
    started = time.perf_counter(); rows = []
    for date in site_days("test"):
        sessions = day_sessions(date); grid = grid_day(grid_date(date))
        truth = make_cars(sessions, sessions.departure_h.to_numpy())[0]
        personal = make_cars(sessions, promises(sessions, "lightgbm", level)[0])[0]
        population = make_cars(sessions, promises(sessions, "population", level)[0])[0]
        for case in ("nominal", "slow_cars_7kw", "building_load_x2", "requests_unknown", "decision_delay_30min"):
            for cap in CAPS:
                for name, cars, policy in (("equal_share", truth, "equal_share"), ("gridproof_priority", personal, "edf"),
                                           ("priority_population_model", population, "edf")):
                    rows.append({"day": date, "case": case, "cap": cap, "policy_name": name, **run_case(case, cars, grid, cap, policy, typical)})
    frame = pd.DataFrame(rows)
    g = frame.groupby(["case", "cap", "policy_name"])
    out = g[["served", "sessions", "unserved_kwh", "requested_kwh", "cap_exceeded_slots"]].sum()
    out["served_pct"] = 100 * out.served / out.sessions
    out["unserved_pct"] = 100 * out.unserved_kwh / out.requested_kwh
    out["emissions_kgco2_per_day"] = g.emissions_kgco2.mean()
    out = out.reset_index()
    out.to_csv(OUT / "sensitivity.csv", index=False)
    table = out.pivot_table(index=["case", "cap"], columns="policy_name", values="served_pct").round(2)
    print(table.to_string())
    print(f"{time.perf_counter() - started:.0f} s")


if __name__ == "__main__":
    main()
