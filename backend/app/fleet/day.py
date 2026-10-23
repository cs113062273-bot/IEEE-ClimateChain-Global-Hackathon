"""Assemble one car-park day: real sessions + departure promises + GB grid day."""
from __future__ import annotations
import numpy as np
from .controller import Car, deliverable_kwh, DT
from .sessions import day_sessions, grid_date
from .grid import grid_day


def make_cars(sessions, promises_h, charger_kw=11.0, risks=None):
    """`promises_h`: decision-time deliver-by hour per session (same order).

    A car's power limit is the charger rating unless the real session shows a
    higher average rate. Requests are clipped to what the car could physically
    receive between the first decision slot after plug-in and its real departure
    at full power, so every request is servable by uncontrolled charging.
    """
    cars, clipped = [], 0
    risks = risks if risks is not None else [()] * len(sessions)
    for row, promise, risk in zip(sessions.itertuples(), promises_h, risks):
        max_kw = max(charger_kw, row.energy_kwh / max(row.dwell_h, 1e-6))
        car = Car(id=row.session_id, driver=row.driver, arrival_h=float(row.arrival_h), request_kwh=float(row.energy_kwh),
                  max_kw=float(max_kw), promise_h=float(max(promise, row.arrival_h)), risk=tuple(risk), departure_h=float(row.departure_h))
        servable = deliverable_kwh(car)
        if servable < car.request_kwh - 1e-9:
            car.request_kwh = float(servable); clipped += 1
        if car.request_kwh > 1e-6:
            cars.append(car)
    return cars, clipped


def load_day(date, promise_fn, solar_kwp=20.0, charger_kw=11.0):
    sessions = day_sessions(date)
    gdate = grid_date(date)
    if gdate is None:
        raise ValueError(f"No GB grid day mapped for {date}")
    promises = promise_fn(sessions)
    cars, clipped = make_cars(sessions, promises, charger_kw)
    return cars, grid_day(gdate, solar_kwp), {"session_date": date, "grid_date": gdate, "clipped_requests": clipped}
