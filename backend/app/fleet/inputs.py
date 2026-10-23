"""Decision-time car inputs: nothing here is derived from the real departure.

Every car has the charger's fixed 11 kW limit and declares its request at
plug-in (the energy the real session took; the data has no state of charge).
Requests are never capped or dropped, so a request that cannot be met before
the real departure stays in the denominator. `infeasible` is a hindsight label
for reporting only; no decision uses it.
"""
from __future__ import annotations
from .controller import Car, deliverable_kwh, SERVED_TOL_KWH

CHARGER_KW = 11.0
TRANSFORM = "declared-request-fixed-11kw-v1"


def decision_cars(sessions, promises_h, risks=None):
    risks = risks if risks is not None else [()] * len(sessions)
    return [Car(id=row.session_id, driver=row.driver, arrival_h=float(row.arrival_h), request_kwh=float(row.energy_kwh),
                max_kw=CHARGER_KW, promise_h=float(max(p, row.arrival_h)), risk=tuple(r), departure_h=float(row.departure_h))
            for row, p, r in zip(sessions.itertuples(), promises_h, risks)]


def possible_kwh(car):
    """Hindsight: the most any schedule could deliver before the real departure."""
    return deliverable_kwh(car)


def infeasible(car):
    return possible_kwh(car) < car.request_kwh - SERVED_TOL_KWH
