"""Workplace car-park controller: information boundary, physics, events, model and evidence."""
import copy
import math
import numpy as np
import pandas as pd
import pytest
from backend.app.fleet.controller import Car, Site, simulate, shortfall_bound, deliverable_kwh, DT, T
from backend.app.fleet.departure import history_features, DepartureDistribution, PopulationQuantile
from backend.app.fleet.sessions import available, grid_date

POLICIES = ["equal_share", "edf", "llf", "optimised"]


def grid(base=7.0):
    hours = (np.arange(T) + .5) * DT
    return {"base_load": np.full(T, base), "tariff": np.where(hours < 7, .12, .23), "ci_forecast": 200 + 50 * np.sin(hours / 3),
            "ci_actual": 210 + 40 * np.sin(hours / 3), "pv_forecast": np.zeros(T), "pv_outcome": np.where((hours > 8) & (hours < 16), 4.0, 0.0),
            "start_utc": [f"2025-03-03T{int(h):02d}:{'30' if (h * 2) % 2 else '00'}:00Z" for h in np.arange(T) * DT]}


def fleet(seed=1, n=14):
    rng = np.random.default_rng(seed); cars = []
    for i in range(n):
        arrival = float(rng.uniform(6, 9)); dwell = float(rng.uniform(1.5, 9))
        car = Car(id=f"{i:012x}", driver=f"EV{i}", arrival_h=arrival, request_kwh=float(rng.uniform(5, 40)), max_kw=11.0,
                  promise_h=arrival + max(1.0, dwell - 1.5), risk=((arrival + .5, .05), (arrival + dwell * .7, .45), (arrival + dwell, .5)),
                  departure_h=arrival + dwell)
        car.request_kwh = min(car.request_kwh, deliverable_kwh(car))
        cars.append(car)
    return cars


@pytest.mark.parametrize("policy", POLICIES)
def test_cap_holds_with_zero_solar(policy):
    result = simulate(fleet(), grid(), Site(connection_kw=60), policy, record=True)
    assert result["cap_exceeded_slots"] == 0
    assert np.all(result["envelope"] <= 60 * DT + 1e-6)


def test_uncontrolled_serves_clipped_requests_but_ignores_cap():
    result = simulate(fleet(), grid(), Site(connection_kw=60), "uncontrolled")
    assert result["served"] == result["sessions"] and result["unserved_kwh"] < 1e-9
    assert result["cap_exceeded_slots"] > 0


@pytest.mark.parametrize("policy", POLICIES)
def test_future_departure_cannot_change_earlier_decisions(policy):
    """Information boundary: decisions before a car leaves never depend on when it will leave."""
    cars = fleet(); probe = max(cars, key=lambda c: c.departure_h - c.arrival_h)
    later = copy.deepcopy(cars); next(c for c in later if c.id == probe.id).departure_h += 2.0
    a = simulate(cars, grid(), Site(connection_kw=60), policy, record=True)
    b = simulate(later, grid(), Site(connection_kw=60), policy, record=True)
    cut = int(math.floor(probe.departure_h / DT))  # last slot start at which both cars are still connected
    assert np.allclose(a["executed"][:, :cut], b["executed"][:, :cut], atol=1e-9)


@pytest.mark.parametrize("policy", POLICIES)
def test_future_arrival_cannot_change_earlier_decisions(policy):
    cars = fleet(); last = max(cars, key=lambda c: c.arrival_h)
    without = [c for c in cars if c.id != last.id]
    a = simulate(cars, grid(), Site(connection_kw=60), policy, record=True)
    b = simulate(without, grid(), Site(connection_kw=60), policy, record=True)
    keep = [i for i, c in enumerate(cars) if c.id != last.id]
    cut = int(math.floor(last.arrival_h / DT)) + 1  # visible only from the first slot start after arrival
    assert np.allclose(a["executed"][keep, :cut], b["executed"][:, :cut], atol=1e-9)


def test_actual_carbon_never_enters_decisions():
    g = grid(); other = dict(g, ci_actual=g["ci_actual"][::-1].copy())
    a = simulate(fleet(), g, Site(connection_kw=60), "optimised", record=True)
    b = simulate(fleet(), other, Site(connection_kw=60), "optimised", record=True)
    assert np.allclose(a["executed"], b["executed"]) and a["emissions_kgco2"] != b["emissions_kgco2"]


def test_shortfall_bound_matches_hand_calculation():
    car = Car("aaaaaaaaaaaa", "EV1", 8.0, 20.0, 11.0, 9.0, departure_h=17.0)
    assert shortfall_bound(16, [car], np.array([20.0]), grid(), np.full(T, 1000.0)) == pytest.approx([9.0])
    assert shortfall_bound(16, [car], np.array([11.0]), grid(), np.full(T, 1000.0)) == pytest.approx([0.0])
    # Base load 7 kWh per half-hour is 14 kW; a 20 kW cap leaves 6 kW = 3 kWh per slot, 6 kWh by 09:00.
    assert shortfall_bound(16, [car], np.array([20.0]), grid(base=7.0), np.full(T, 20.0)) == pytest.approx([14.0])


@pytest.mark.parametrize("policy", POLICIES)
def test_events_never_rewrite_executed_energy(policy):
    cars = fleet(); at = 18
    target = next(c for c in cars if c.arrival_h <= at * DT < c.departure_h)
    events = [{"type": "cap", "at_slot": at, "from_slot": at, "to_slot": at + 6, "kw": 30},
              {"type": "leave", "at_slot": at, "car_id": target.id, "departure_h": at * DT + 1.0}]
    base = simulate(cars, grid(), Site(connection_kw=60), policy, record=True)
    changed = simulate(cars, grid(), Site(connection_kw=60), policy, events=events, record=True)
    assert np.allclose(base["executed"][:, :at], changed["executed"][:, :at])
    assert np.all(changed["envelope"][at:at + 6] <= 30 * DT + 1e-6)
    i = [c.id for c in cars].index(target.id)
    assert changed["executed"][i, at + 2:].sum() == 0  # left at the declared time
    assert cars[i].departure_h == target.departure_h  # caller's cars are not mutated


def test_declared_departure_raises_queue_rank_without_guaranteeing_service():
    """A declaration becomes the car's deadline; cars already past their target still rank first."""
    cars = fleet(); at = 16
    target = max((c for c in cars if c.arrival_h <= at * DT < c.departure_h), key=lambda c: c.promise_h)
    event = [{"type": "leave", "at_slot": at, "car_id": target.id, "departure_h": at * DT + 1.5}]
    plain = simulate(cars, grid(), Site(connection_kw=40), "edf", record=True)
    declared = simulate(cars, grid(), Site(connection_kw=40), "edf", events=event, record=True)
    rank = lambda r: r["trace"][at]["priority"].index(target.id) if target.id in r["trace"][at]["priority"] else len(cars)
    assert rank(declared) <= rank(plain)


def test_decision_time_inputs_never_depend_on_the_real_departure():
    from backend.app.fleet.inputs import decision_cars, infeasible
    sessions = pd.DataFrame({"session_id": ["aaaaaaaaaaaa", "bbbbbbbbbbbb"], "driver": ["EV1", "EV2"], "arrival_h": [7.0, 8.0],
                             "energy_kwh": [30.0, 60.0], "departure_h": [16.0, 10.0]})
    later = sessions.assign(departure_h=[18.0, 12.0])
    strip = lambda cars: [(c.arrival_h, c.request_kwh, c.max_kw, c.promise_h) for c in cars]
    assert strip(decision_cars(sessions, [12.0, 12.0])) == strip(decision_cars(later, [12.0, 12.0]))
    cars = decision_cars(sessions, [12.0, 12.0])
    assert [c.max_kw for c in cars] == [11.0, 11.0] and [c.request_kwh for c in cars] == [30.0, 60.0]  # never capped
    assert [infeasible(c) for c in cars] == [False, True]  # 60 kWh in 2 h at 11 kW is impossible; kept, not dropped


def test_history_features_use_only_earlier_dates():
    rows = []
    for d, dwell in [("2022-01-03", 8), ("2022-01-03", 2), ("2022-01-04", 7), ("2022-01-05", 6), ("2022-01-06", 9)]:
        start = pd.Timestamp(d + " 07:00", tz="UTC")
        rows.append({"driver": "EV1", "date": d, "start_utc": start, "arrival_h": 7.0, "weekday": start.weekday(), "dwell_h": float(dwell), "departure_h": 7.0 + dwell})
    df = pd.DataFrame(rows)
    X = history_features(df)
    assert list(X.n_prior) == [0, 0, 2, 3, 4]  # same-day sessions never see each other
    assert np.isnan(X.dwell_median[2]) and X.dwell_median[3] == pytest.approx(7.0) and X.dwell_median[4] == pytest.approx(6.5)


def test_departure_distribution_is_monotone_and_calibrated_in_sample():
    rng = np.random.default_rng(0); n = 3000
    df = pd.DataFrame({"arrival_h": rng.uniform(6, 9, n), "dwell_h": rng.gamma(6, 1.2, n), "date": "2022-01-01", "weekday": 0})
    model = DepartureDistribution("population").fit(df, df).calibrate(df, df)
    q = model.quantiles(df, df)
    assert np.all(np.diff(q, axis=1) >= -1e-12)
    for level, share in model.coverage(df, df).items():
        assert abs(share - float(level)) < .02
    points = model.risk_points(7.0, q[0])
    assert sum(w for _, w in points) == pytest.approx(1.0) and points[0][0] == 7.5


def test_grid_mapping_keeps_weekday_and_never_leaves_2025():
    for d in ["2023-03-15", "2024-06-04", "2024-10-02"]:
        mapped = grid_date(d)
        assert pd.Timestamp(mapped).weekday() == pd.Timestamp(d).weekday() and mapped.startswith("2025")
    assert grid_date("2022-06-01") is None and grid_date("2024-01-02") is None


@pytest.mark.skipif(not available(), reason="Licensed session data not downloaded")
def test_real_day_record_verifies_and_both_forgeries_fail():
    from backend.app.fleet.service import run_day, DayRequest, default_day
    from backend.app.fleet import evidence as E
    day = run_day(DayRequest(date=default_day(), connection_kw=110, mode="equal_share"))
    proof = E.build(day["run_id"])
    check = E.verify(proof["evidence"], proof["digest"])
    assert check["verified"], check["errors"]
    hide = E.forge(proof["evidence_id"], "hide_shortfall")["rehashed_verification"]
    assert hide["levels"]["integrity"]["verified"] and not hide["verified"]
    assert not hide["levels"]["physical_service"]["verified"] or not hide["levels"]["decision_replay"]["verified"]
    move = E.forge(proof["evidence_id"], "move_departure")["rehashed_verification"]
    assert move["levels"]["integrity"]["verified"] and move["levels"]["decision_replay"]["verified"]
    assert move["levels"]["source_lineage"]["status"] == "MISMATCH" and not move["verified"]


@pytest.mark.skipif(not available(), reason="Licensed session data not downloaded")
def test_record_that_omits_drivers_is_rejected_even_when_recomputed():
    """Regression for an external review: keep 1 of the day's cars, recompute consistently, rehash."""
    from backend.app.fleet.service import run_day, DayRequest, default_day
    from backend.app.fleet import evidence as E
    from backend.app.services.evidence import normalize, digest
    day = run_day(DayRequest(date=default_day(), connection_kw=100, mode="equal_share"))
    proof = E.build(day["run_id"])
    forged = copy.deepcopy(proof["evidence"]); keep = forged["decision_inputs"]["cars"][0]
    forged["decision_inputs"]["cars"] = [keep]
    forged["outcomes"]["departures_h"] = {keep["id"]: forged["outcomes"]["departures_h"][keep["id"]]}
    executed, _, _ = E.verify_carpark.replay("equal_share", forged["decision_inputs"], forged["outcomes"])
    forged["record"]["executed_kwh"] = executed
    forged["results"]["per_car"] = {keep["id"]: {"delivered_kwh": sum(executed[keep["id"]]), "unserved_kwh": max(0.0, float(keep["request_kwh"]) - sum(executed[keep["id"]]))}}
    forged["results"]["sessions"] = 1
    E._recompute_results(forged)
    forged = normalize(forged)
    result = E.verify(forged, "0x" + digest(forged))
    assert all(result["levels"][k]["verified"] for k in ("integrity", "physical_service", "decision_replay"))
    assert result["levels"]["source_lineage"]["status"] == "MISMATCH" and not result["verified"]
    assert any("missing from the record" in e for e in result["levels"]["source_lineage"]["errors"])
    assert not E.forge(proof["evidence_id"], "drop_sessions")["rehashed_verification"]["verified"]


@pytest.mark.skipif(not available(), reason="Licensed session data not downloaded")
def test_tampered_promise_is_caught_by_decision_replay():
    from backend.app.fleet.service import run_day, DayRequest, default_day
    from backend.app.fleet import evidence as E
    from backend.app.services.evidence import normalize, digest
    day = run_day(DayRequest(date=default_day(), connection_kw=100, mode="priority"))
    proof = E.build(day["run_id"])
    forged = copy.deepcopy(proof["evidence"])
    for car in forged["decision_inputs"]["cars"]:  # claim the controller had looser targets
        car["promise_h"] = "23.000000000"
    forged = normalize(forged)
    result = E.verify(forged, "0x" + digest(forged))
    assert result["levels"]["integrity"]["verified"] and result["levels"]["decision_replay"]["status"] == "MISMATCH"
