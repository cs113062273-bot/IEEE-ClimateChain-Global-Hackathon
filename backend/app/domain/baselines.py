"""Frozen battery-equipped baselines shared by product and evaluation."""
import time
import numpy as np
from .solver import DT, T, TOL, _dispatch, _result

def heuristic(scenario, intervals, policy):
    """EDF jobs, slot greediness, contiguous batch, loss-aware battery transfers.

    Battery pair transfers honor both endpoint SoCs and every intermediate SoC.
    Peak uses fixed demand only, without carbon/tariff/solar forecasts. All use
    a conservative zero-PV capacity bound; no future outcomes enter decisions.
    """
    started = time.perf_counter()
    fixed = np.array([x["fixed_load_kwh"] for x in intervals])
    pv = np.array([x["pv_forecast_kwh"] for x in intervals])
    score = np.array([x["ci_forecast_g_per_kwh"] if policy == "greedy_carbon"
                      else x["tariff_gbp_per_kwh"] for x in intervals])
    net = fixed.copy()
    ev = np.zeros((len(scenario.ev_jobs), T))
    batch = np.zeros(T)
    occupancy = np.zeros(T)
    starts = {}
    cap = min(scenario.max_grid_import_kw, scenario.peak_cap_kw or np.inf) * DT
    for job in sorted(scenario.batch_jobs, key=lambda j:(j.latest_end_slot, j.id)):
        candidates = []
        for start in range(job.earliest_start_slot, job.latest_end_slot-job.duration_slots+1):
            window = slice(start, start+job.duration_slots)
            proposed = net.copy()
            proposed[window] += job.energy_kwh/job.duration_slots
            if np.any(occupancy[window] >= scenario.max_batch_concurrency) or proposed.max() > cap+TOL:
                continue
            value = proposed.max() if policy == "peak_heuristic" else score[window].sum()
            candidates.append((value, start))
        if not candidates:
            return None, "No feasible greedy batch placement"
        start = min(candidates)[1]
        starts[job.id] = start
        window = slice(start, start+job.duration_slots)
        occupancy[window] += 1
        batch[window] += job.energy_kwh/job.duration_slots
        net[window] += job.energy_kwh/job.duration_slots
    for j in sorted(range(len(scenario.ev_jobs)), key=lambda j:(scenario.ev_jobs[j].deadline_slot, scenario.ev_jobs[j].id)):
        job = scenario.ev_jobs[j]
        remaining = job.energy_kwh
        while remaining > TOL:
            available = [(t, min(job.max_kw*DT-ev[j,t], scenario.charger_station_kw*DT-ev[:,t].sum(), cap-net[t]))
                         for t in range(job.arrival_slot, job.deadline_slot)]
            available = [(t, room) for t, room in available if room > TOL]
            if not available:
                return None, f"Greedy cannot complete {job.id}; remaining {remaining:.6f} kWh"
            t, room = min(available, key=lambda pair:(net[pair[0]] if policy == "peak_heuristic" else score[pair[0]], pair[0]))
            take = min(remaining, room, .1 if policy == "peak_heuristic" else np.inf)
            ev[j,t] += take
            net[t] += take
            remaining -= take
    charge = np.zeros(T)
    discharge = np.zeros(T)
    soc = np.full(T+1, scenario.battery_capacity_kwh*scenario.soc_initial_fraction)
    ratio = scenario.eta_charge*scenario.eta_discharge
    if scenario.battery_capacity_kwh:
        pairs = [(a, b) for a in range(T) for b in range(T) if a != b]
        if policy != "peak_heuristic":
            pairs.sort(key=lambda ab:(-(ratio*score[ab[1]]-score[ab[0]]), ab))
        else:
            pairs.sort(key=lambda ab:(-(net[ab[1]]-net[ab[0]]), ab))
        for a, b in pairs:
            gain = net[b]-net[a] if policy == "peak_heuristic" else ratio*score[b]-score[a]
            if gain <= 1e-9 or discharge[a] > TOL or charge[b] > TOL:
                continue
            # Nonexporting discharge is bounded by predetermined demand. Using
            # forecast PV for carbon/cost battery allocation is legitimate.
            residual = net[b] if policy == "peak_heuristic" else max(0, net[b]-pv[b])
            amount = min(scenario.charge_kw*DT-charge[a], (scenario.discharge_kw*DT-discharge[b])/ratio,
                         residual/ratio, cap-net[a])
            if policy == "peak_heuristic":
                amount = min(amount, gain/(1+ratio))
            lo, hi = min(a,b)+1, max(a,b)+1
            if a < b:
                room = (scenario.battery_capacity_kwh*scenario.soc_max_fraction-soc[lo:hi]).min()
            else:
                room = (soc[lo:hi]-scenario.battery_capacity_kwh*scenario.soc_min_fraction).min()
            amount = max(0, min(amount, room/scenario.eta_charge))
            charge[a] += amount
            discharge[b] += ratio*amount
            net[a] += amount
            net[b] -= ratio*amount
            soc[lo:hi] += (1 if a < b else -1)*scenario.eta_charge*amount
    used = np.minimum(pv, np.maximum(net, 0))
    dispatch = _dispatch(intervals, np.maximum(net-used, 0), charge, discharge, soc, ev, batch, used, pv-used)
    plan = _result(scenario, dispatch, starts, policy, started, "heuristic", None,
                   "EDF, greedy slots, exact-terminal-SoC battery pair transfers; no MILP")
    return plan, None

