"""REP-1A: tests for the staff fleet utilization summary.

Every test gets a fresh temporary SQLite database (see the `client` fixture),
seeded with the standard 12-car demo fleet by main.py's startup code.

Most tests insert reservations straight into the database instead of going
through POST /reservations. That lets us use past dates and the "cancelled"
status freely, which the customer API (correctly) does not allow.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

import main
from fleet_utilization import overlap_days, percentage
from models import Reservation, Vehicle

STAFF_KEY = "rep1a-secret"
URL = "/staff/reports/utilization"

# A fixed 10-day report window used by most tests: Nov 1 to Nov 10 inclusive.
P_START = date(2026, 11, 1)
P_END = date(2026, 11, 10)
PERIOD = {"start_date": P_START.isoformat(), "end_date": P_END.isoformat()}


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point the app at a throwaway database and set the staff key."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'utilization.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setenv("STAFF_API_KEY", STAFF_KEY)
    with TestClient(main.app) as test_client:
        yield test_client
    engine.dispose()


def headers():
    return {"X-Staff-Key": STAFF_KEY}


def fleet_ids():
    """Ids of the seeded demo vehicles, in id order."""
    with Session(main.engine) as session:
        return list(session.exec(select(Vehicle.id).order_by(Vehicle.id)).all())


def reserve(vehicle_id, start, end, status="confirmed"):
    """Insert a reservation row directly (bypasses customer-side validation)."""
    with Session(main.engine) as session:
        session.add(Reservation(
            vehicle_id=vehicle_id, customer_name="Report Test",
            start_date=start, end_date=end, status=status,
        ))
        session.commit()


def report(client, **params):
    response = client.get(URL, headers=headers(), params={**PERIOD, **params})
    assert response.status_code == 200, response.text
    return response.json()


def row_for(data, vehicle_id):
    return next(row for row in data["vehicles"] if row["vehicle_id"] == vehicle_id)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def test_overlap_days_clips_to_period():
    start, end_excl = date(2026, 11, 1), date(2026, 11, 11)
    assert overlap_days(date(2026, 11, 2), date(2026, 11, 5), start, end_excl) == 3   # fully inside
    assert overlap_days(date(2026, 10, 28), date(2026, 11, 3), start, end_excl) == 2  # starts before
    assert overlap_days(date(2026, 11, 9), date(2026, 11, 15), start, end_excl) == 2  # ends after
    assert overlap_days(date(2026, 10, 1), date(2026, 12, 1), start, end_excl) == 10  # covers it all
    assert overlap_days(date(2026, 10, 25), date(2026, 11, 1), start, end_excl) == 0  # returned on day 1
    assert overlap_days(date(2026, 12, 1), date(2026, 12, 5), start, end_excl) == 0   # entirely after


def test_percentage_rounds_and_handles_zero():
    assert percentage(1, 3) == 33.3
    assert percentage(0, 0) == 0.0


# ---------------------------------------------------------------------------
# Access control and validation
# ---------------------------------------------------------------------------
def test_staff_key_is_required(client):
    assert client.get(URL, params=PERIOD).status_code == 401
    assert client.get(URL, params=PERIOD, headers={"X-Staff-Key": "wrong"}).status_code == 401


@pytest.mark.parametrize("params", [
    {"start_date": "2026-11-10", "end_date": "2026-11-01"},  # end before start
    {"start_date": "2026-11-01"},                            # end missing
    {"end_date": "2026-11-01"},                              # start missing
    {"start_date": "2025-01-01", "end_date": "2026-11-01"},  # longer than 366 days
])
def test_invalid_periods_are_rejected(client, params):
    response = client.get(URL, headers=headers(), params=params)
    assert response.status_code == 400, response.text


def test_defaults_to_last_30_days(client):
    data = client.get(URL, headers=headers()).json()
    assert data["end_date"] == date.today().isoformat()
    assert data["period_days"] == 30


# ---------------------------------------------------------------------------
# Utilization maths
# ---------------------------------------------------------------------------
def test_empty_fleet_period_reports_zero_utilization(client):
    data = report(client)
    vehicle_count = len(fleet_ids())  # 12 demo cars
    assert data["period_days"] == 10
    assert data["fleet"] == {
        "vehicle_count": vehicle_count,
        "booked_days": 0,
        "available_days": vehicle_count * 10,
        "utilization_pct": 0.0,
        "idle_vehicle_count": vehicle_count,
    }


def test_fleet_vehicle_and_category_totals_match_hand_calculation(client):
    first, second = fleet_ids()[:2]  # seeded Corolla and Civic, both "compact"
    reserve(first, date(2026, 11, 1), date(2026, 11, 6))   # 5 days
    reserve(second, date(2026, 11, 3), date(2026, 11, 4))  # 1 day

    data = report(client)
    vehicle_count = len(fleet_ids())

    # Per vehicle: 5/10 = 50%, 1/10 = 10%
    assert row_for(data, first)["booked_days"] == 5
    assert row_for(data, first)["utilization_pct"] == 50.0
    assert row_for(data, second)["utilization_pct"] == 10.0

    # Fleet: 6 booked out of 12 cars x 10 days = 120 -> 5.0%
    assert data["fleet"]["booked_days"] == 6
    assert data["fleet"]["available_days"] == vehicle_count * 10
    assert data["fleet"]["utilization_pct"] == 5.0
    assert data["fleet"]["idle_vehicle_count"] == vehicle_count - 2

    # The compact category gets all 6 booked days.
    compact = next(c for c in data["categories"] if c["category"] == "compact")
    assert compact["booked_days"] == 6
    assert compact["utilization_pct"] == percentage(6, compact["vehicle_count"] * 10)


def test_partial_overlaps_are_clipped_to_the_period(client):
    vid = fleet_ids()[0]
    reserve(vid, date(2026, 10, 28), date(2026, 11, 3))   # 2 days inside (Nov 1, 2)
    reserve(vid, date(2026, 11, 9), date(2026, 11, 15))   # 2 days inside (Nov 9, 10)
    reserve(vid, date(2026, 10, 20), date(2026, 11, 1))   # returned Nov 1 -> 0 days
    row = row_for(report(client), vid)
    assert row["booked_days"] == 4
    assert row["reservation_count"] == 2  # the zero-day booking is not counted


def test_cancelled_reservations_are_ignored(client):
    vid = fleet_ids()[0]
    reserve(vid, date(2026, 11, 1), date(2026, 11, 6), status="cancelled")
    row = row_for(report(client), vid)
    assert row["booked_days"] == 0
    assert row["reservation_count"] == 0


def test_vehicles_sorted_busiest_first(client):
    a, b, c = fleet_ids()[:3]
    reserve(a, date(2026, 11, 1), date(2026, 11, 2))  # 1 day
    reserve(b, date(2026, 11, 1), date(2026, 11, 8))  # 7 days
    reserve(c, date(2026, 11, 1), date(2026, 11, 4))  # 3 days
    order = [row["vehicle_id"] for row in report(client)["vehicles"][:3]]
    assert order == [b, c, a]


def test_archived_vehicles_are_hidden_unless_requested(client):
    vid = fleet_ids()[0]
    reserve(vid, date(2026, 11, 1), date(2026, 11, 3))
    archived = client.patch(f"/vehicles/{vid}/archive", headers=headers())
    assert archived.status_code == 200

    default = report(client)
    assert vid not in [row["vehicle_id"] for row in default["vehicles"]]
    assert default["fleet"]["booked_days"] == 0

    included = report(client, include_archived="true")
    assert row_for(included, vid)["archived"] is True
    assert row_for(included, vid)["booked_days"] == 2


# ---------------------------------------------------------------------------
# Integration with the customer reservation flow (USER-1, USER-7, USER-3)
# ---------------------------------------------------------------------------
def test_report_follows_real_bookings_through_modify_and_cancel(client):
    """Create a booking through the public API, modify it, then cancel it,
    and check the report reflects each step."""
    vid = fleet_ids()[0]
    start = date.today() + timedelta(days=5)
    window = {"start_date": start.isoformat(), "end_date": (start + timedelta(days=9)).isoformat()}

    booking = {
        "vehicle_id": vid,
        "customer_name": "Integration Test",
        "driver_license_number": "D1234567",
        "driver_license_expiry": (start + timedelta(days=400)).isoformat(),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=2)).isoformat(),  # 2 days
    }
    created = client.post("/reservations", json=booking)
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]
    token = {"X-Booking-Token": created.json()["management_token"]}

    def booked_days():
        response = client.get(URL, headers=headers(), params=window)
        return row_for(response.json(), vid)["booked_days"]

    assert booked_days() == 2  # USER-1: new booking is counted

    extended = {**booking, "end_date": (start + timedelta(days=4)).isoformat()}
    assert client.put(f"/reservations/{reservation_id}", headers=token, json=extended).status_code == 200
    assert booked_days() == 4  # USER-7: modified dates are counted

    assert client.post(f"/reservations/{reservation_id}/cancel", headers=token).status_code == 200
    assert booked_days() == 0  # USER-3: cancelled booking drops out
