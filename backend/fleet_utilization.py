"""REP-1A: staff-only fleet utilization summary.

What this module answers for a manager:
    "Over this date range, how much of the fleet was actually rented out?"

Utilization for one vehicle is:

        booked days in the period
        -------------------------  x 100
        days in the period

The same ratio is then rolled up per category (e.g. all SUVs) and for the
whole fleet, by summing booked days and available days before dividing.
(Summing first, then dividing, weights every vehicle-day equally, so a
category with 5 cars is not skewed by a single idle car.)

Day-counting rules (kept consistent with the rest of the API):
    * A reservation occupies the nights from start_date up to, but NOT
      including, end_date. A booking from Nov 1 -> Nov 4 is 3 days, exactly
      the number of days USER-1/USER-6 bill for.
    * The report period is INCLUSIVE on both ends, because that is how a
      manager reads it: "Nov 1 to Nov 30" means all 30 days of November.
    * Reservations that only partly overlap the period are clipped, so only
      the days inside the period count. Utilization can never exceed 100%.
    * Only "confirmed" reservations count. Cancelled ones (USER-3) are ignored.
      Modified ones (USER-7) are counted with their current dates, because
      USER-7 updates the reservation row in place.

This module creates NO new tables. It only reads the existing Vehicle and
Reservation tables, so it cannot conflict with other stories' schemas.
It follows the same registration pattern as REP-2B (vehicle_maintenance.py):
main.py passes in the engine getter and the shared require_staff dependency.
"""
from datetime import date, timedelta
from typing import Callable

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session, SQLModel, select

from models import Reservation, Vehicle

# Upper bound on the report window. One year (plus a leap day) is plenty for a
# fleet summary and stops someone from requesting a 100-year range by mistake.
MAX_PERIOD_DAYS = 366

# When the page loads with no dates chosen, show the last 30 days, ending today.
DEFAULT_PERIOD_DAYS = 30


# ---------------------------------------------------------------------------
# Response shapes (what the frontend receives as JSON)
# ---------------------------------------------------------------------------
class UtilizationTotals(SQLModel):
    """Totals shared by the fleet-wide row and each category row."""

    vehicle_count: int
    booked_days: int
    available_days: int
    utilization_pct: float
    # Vehicles with zero booked days in the period: the "underused" signal.
    idle_vehicle_count: int


class CategoryUtilization(UtilizationTotals):
    category: str


class VehicleUtilization(SQLModel):
    vehicle_id: int
    make: str
    model: str
    category: str
    archived: bool
    reservation_count: int
    booked_days: int
    available_days: int
    utilization_pct: float


class FleetUtilizationReport(SQLModel):
    start_date: date
    end_date: date  # inclusive
    period_days: int
    fleet: UtilizationTotals
    categories: list[CategoryUtilization]
    vehicles: list[VehicleUtilization]


# ---------------------------------------------------------------------------
# Pure helper functions (no database, easy to unit test)
# ---------------------------------------------------------------------------
def percentage(booked_days: int, available_days: int) -> float:
    """Return booked/available as a percentage rounded to one decimal place.

    An empty denominator (no vehicles in a category) returns 0.0 instead of
    raising ZeroDivisionError.
    """
    if available_days <= 0:
        return 0.0
    return round(booked_days / available_days * 100, 1)


def overlap_days(res_start: date, res_end: date, period_start: date, period_end_exclusive: date) -> int:
    """Count the days a reservation spends inside the report period.

    Both ranges are treated as half-open [start, end), so we clip the
    reservation to the period and measure what is left:

        period:        |-------------|
        reservation: |-----|            -> only the part inside the bars counts

    If the reservation is entirely outside, the clipped range is empty
    (or negative), and max(0, ...) turns that into 0.
    """
    clipped_start = max(res_start, period_start)
    clipped_end = min(res_end, period_end_exclusive)
    return max(0, (clipped_end - clipped_start).days)


def summarize(rows: list[VehicleUtilization]) -> UtilizationTotals:
    """Roll a list of per-vehicle rows up into one totals row."""
    booked = sum(row.booked_days for row in rows)
    available = sum(row.available_days for row in rows)
    return UtilizationTotals(
        vehicle_count=len(rows),
        booked_days=booked,
        available_days=available,
        utilization_pct=percentage(booked, available),
        idle_vehicle_count=sum(1 for row in rows if row.booked_days == 0),
    )


def resolve_period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    """Validate the requested range, or fall back to the last 30 days."""
    # Same rule as GET /vehicles (USER-5): both dates or neither.
    if (start_date is None) != (end_date is None):
        raise HTTPException(status_code=400, detail="Start and end dates must be given together")
    if start_date is None:
        end_date = date.today()
        start_date = end_date - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    if (end_date - start_date).days + 1 > MAX_PERIOD_DAYS:
        raise HTTPException(
            status_code=400, detail=f"Report period cannot be longer than {MAX_PERIOD_DAYS} days"
        )
    return start_date, end_date


# ---------------------------------------------------------------------------
# Route registration (called once from main.py)
# ---------------------------------------------------------------------------
def register_utilization_routes(app: FastAPI, get_engine: Callable, require_staff: Callable) -> None:
    """Attach the REP-1A endpoint to the app.

    get_engine is a function (not the engine itself) so tests can swap
    main.engine for a temporary database and this module picks it up.
    """
    router = APIRouter(prefix="/staff/reports", tags=["Fleet reports"])

    @router.get(
        "/utilization",
        response_model=FleetUtilizationReport,
        dependencies=[Depends(require_staff)],  # 401 without a valid X-Staff-Key
    )
    def fleet_utilization(
        start_date: date | None = None,
        end_date: date | None = None,
        # Archived cars are hidden by default because they are no longer part
        # of the rentable fleet. Staff can opt in to see their past usage.
        include_archived: bool = Query(default=False),
    ):
        period_start, period_end = resolve_period(start_date, end_date)
        # Convert the inclusive end into an exclusive one so the maths in
        # overlap_days matches how reservations store their end_date.
        period_end_exclusive = period_end + timedelta(days=1)
        period_days = (period_end_exclusive - period_start).days

        with Session(get_engine()) as session:
            vehicle_query = select(Vehicle).order_by(Vehicle.id)
            if not include_archived:
                vehicle_query = vehicle_query.where(Vehicle.archived == False)  # noqa: E712
            vehicles = session.exec(vehicle_query).all()

            # Fetch only confirmed reservations that touch the period, using the
            # same overlap test USER-1 uses for double-booking checks.
            reservations = session.exec(
                select(Reservation).where(
                    Reservation.status == "confirmed",
                    Reservation.start_date < period_end_exclusive,
                    Reservation.end_date > period_start,
                )
            ).all()

        # Group booked days and booking counts by vehicle id.
        booked_by_vehicle: dict[int, int] = {}
        count_by_vehicle: dict[int, int] = {}
        for reservation in reservations:
            days = overlap_days(
                reservation.start_date, reservation.end_date, period_start, period_end_exclusive
            )
            booked_by_vehicle[reservation.vehicle_id] = booked_by_vehicle.get(reservation.vehicle_id, 0) + days
            count_by_vehicle[reservation.vehicle_id] = count_by_vehicle.get(reservation.vehicle_id, 0) + 1

        vehicle_rows = [
            VehicleUtilization(
                vehicle_id=vehicle.id,
                make=vehicle.make,
                model=vehicle.model,
                category=vehicle.category,
                archived=vehicle.archived,
                reservation_count=count_by_vehicle.get(vehicle.id, 0),
                # min() is a safety net: overlapping confirmed bookings should be
                # impossible (USER-1 blocks them), but never report >100%.
                booked_days=min(booked_by_vehicle.get(vehicle.id, 0), period_days),
                available_days=period_days,
                utilization_pct=percentage(min(booked_by_vehicle.get(vehicle.id, 0), period_days), period_days),
            )
            for vehicle in vehicles
        ]

        # Busiest vehicles first; ties broken by id so the order is stable.
        vehicle_rows.sort(key=lambda row: (-row.utilization_pct, row.vehicle_id))

        # Category breakdown, alphabetical so the table is easy to scan.
        rows_by_category: dict[str, list[VehicleUtilization]] = {}
        for row in vehicle_rows:
            rows_by_category.setdefault(row.category, []).append(row)
        categories = [
            CategoryUtilization(category=category, **summarize(rows).model_dump())
            for category, rows in sorted(rows_by_category.items())
        ]

        return FleetUtilizationReport(
            start_date=period_start,
            end_date=period_end,
            period_days=period_days,
            fleet=summarize(vehicle_rows),
            categories=categories,
            vehicles=vehicle_rows,
        )

    app.include_router(router)
