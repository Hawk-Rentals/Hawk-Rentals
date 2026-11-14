"""USER-5 (Sprint 2 carryover): booking status details and integration with
USER-2 (category), USER-3 (cancellation) and USER-4 (price) filters."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

import main

STAFF = {"X-Staff-Key": "test-staff-key"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "INITIAL_VEHICLES", [])
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
    with TestClient(main.app) as test_client:
        yield test_client
    engine.dispose()


@pytest.fixture
def start():
    return date.today() + timedelta(days=7)


def add_vehicle(client, model="Corolla", category="compact", daily_rate=60, available=True):
    response = client.post(
        "/vehicles",
        headers=STAFF,
        json={"make": "Toyota", "model": model, "category": category,
              "daily_rate": daily_rate, "available": available},
    )
    assert response.status_code == 200
    return response.json()["id"]


def reserve(client, vehicle_id, start, end):
    response = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle_id,
            "customer_name": "Taylor",
            "driver_license_number": "D1234567",
            "driver_license_expiry": (end + timedelta(days=365)).isoformat(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


def search(client, start, end, **params):
    params.update(start_date=start.isoformat(), end_date=end.isoformat())
    response = client.get("/vehicles", params=params)
    assert response.status_code == 200
    return {vehicle["id"]: vehicle for vehicle in response.json()}


def test_booked_vehicle_reports_when_it_is_free_again(client, start):
    car = add_vehicle(client)
    reserve(client, car, start, start + timedelta(days=3))
    result = search(client, start + timedelta(days=1), start + timedelta(days=2))
    assert result[car]["status"] == "booked"
    assert result[car]["booked_until"] == (start + timedelta(days=3)).isoformat()


def test_available_vehicle_has_no_booked_until(client, start):
    car = add_vehicle(client)
    result = search(client, start, start + timedelta(days=2))
    assert result[car]["status"] == "available"
    assert result[car]["booked_until"] is None


def test_back_to_back_bookings_are_chained(client, start):
    car = add_vehicle(client)
    reserve(client, car, start, start + timedelta(days=2))
    reserve(client, car, start + timedelta(days=2), start + timedelta(days=5))
    result = search(client, start, start + timedelta(days=1))
    assert result[car]["booked_until"] == (start + timedelta(days=5)).isoformat()


def test_out_of_service_vehicle_has_no_booked_until(client, start):
    car = add_vehicle(client, available=False)
    result = search(client, start, start + timedelta(days=2))
    assert result[car]["status"] == "unavailable"
    assert result[car]["booked_until"] is None


def test_cancelled_reservation_frees_vehicle(client, start):
    """Integration with USER-3: cancelling a booking makes the car available again."""
    car = add_vehicle(client)
    booking = reserve(client, car, start, start + timedelta(days=3))
    assert search(client, start, start + timedelta(days=3))[car]["status"] == "booked"
    cancel = client.post(
        f"/reservations/{booking['id']}/cancel",
        headers={"X-Booking-Token": booking["management_token"]},
    )
    assert cancel.status_code == 200
    after = search(client, start, start + timedelta(days=3))
    assert after[car]["status"] == "available"
    assert after[car]["booked_until"] is None


def test_hide_booked_combines_with_category_and_price(client, start):
    """Integration with USER-2 and USER-4: all filters apply in one request."""
    cheap_free = add_vehicle(client, model="Corolla", daily_rate=50)
    cheap_booked = add_vehicle(client, model="Yaris", daily_rate=45)
    add_vehicle(client, model="Supra", category="sports", daily_rate=50)
    add_vehicle(client, model="Crown", daily_rate=150)
    reserve(client, cheap_booked, start, start + timedelta(days=2))
    end = start + timedelta(days=2)
    shown = search(client, start, end, category="compact", max_price=100)
    assert set(shown) == {cheap_free, cheap_booked}
    hidden = search(client, start, end, category="compact", max_price=100, status="available")
    assert set(hidden) == {cheap_free}
