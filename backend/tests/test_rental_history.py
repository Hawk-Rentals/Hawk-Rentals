from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

import main
from models import Reservation, Vehicle


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rental_history.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
    with TestClient(main.app) as app_client:
        yield app_client
    engine.dispose()


def book(client, *, offset=5, vehicle_id=1, customer_name="Taylor", duration=3):
    start = date.today() + timedelta(days=offset)
    end = start + timedelta(days=duration)
    response = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle_id,
            "customer_name": customer_name,
            "driver_license_number": "ON123456",
            "driver_license_expiry": (date.today() + timedelta(days=1000)).isoformat(),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def lookup(client, booking, token=None):
    return client.get(
        f"/reservations/{booking['id']}/history",
        headers={"X-Booking-Token": token or booking["management_token"]},
    )


def test_verified_booking_returns_vehicle_dates_state_and_original_estimate(client):
    booking = book(client)
    response = lookup(client, booking)
    assert response.status_code == 200
    history = response.json()
    assert history["id"] == booking["id"]
    assert history["vehicle_id"] == 1
    assert history["vehicle_make"] == "Toyota"
    assert history["vehicle_model"] == "Corolla"
    assert history["customer_name"] == "Taylor"
    assert history["rental_state"] == "upcoming"
    assert history["status"] == "confirmed"
    assert history["booked_daily_rate"] == 55
    assert history["original_total"] == 165
    assert "management_token" not in history
    assert "management_token_hash" not in history
    assert "driver_license_number" not in history


@pytest.mark.parametrize("headers", [{}, {"X-Booking-Token": "wrong"}])
def test_history_requires_valid_booking_access_code(client, headers):
    booking = book(client)
    response = client.get(f"/reservations/{booking['id']}/history", headers=headers)
    assert response.status_code == 404
    assert "customer_name" not in response.json()


def test_other_customers_token_cannot_read_booking(client):
    first = book(client, customer_name="Taylor")
    second = book(client, vehicle_id=2, customer_name="Jordan")
    response = lookup(client, first, second["management_token"])
    assert response.status_code == 404


def test_unknown_booking_returns_not_found(client):
    assert client.get("/reservations/9999/history", headers={"X-Booking-Token": "test"}).status_code == 404


@pytest.mark.parametrize(
    "offset,duration,state",
    [(-6, 2, "completed"), (-1, 3, "ongoing"), (3, 2, "upcoming")],
)
def test_dates_determine_rental_state(client, offset, duration, state):
    booking = book(client, offset=offset, duration=duration)
    assert lookup(client, booking).json()["rental_state"] == state


def test_cancelled_booking_remains_visible_as_cancelled(client):
    booking = book(client)
    assert client.post(
        f"/reservations/{booking['id']}/cancel",
        headers={"X-Booking-Token": booking["management_token"]},
    ).status_code == 200
    history = lookup(client, booking).json()
    assert history["status"] == "cancelled"
    assert history["rental_state"] == "cancelled"
    assert history["original_total"] == 165


def test_price_snapshot_survives_vehicle_rate_change_and_archive(client):
    booking = book(client)
    headers = {"X-Staff-Key": "test-staff-key"}
    assert client.patch(
        "/vehicles/1",
        headers=headers,
        json={"daily_rate": 160},
    ).status_code == 200
    assert client.patch("/vehicles/1/archive", headers=headers).status_code == 200
    history = lookup(client, booking).json()
    assert history["vehicle_make"] == "Toyota"
    assert history["booked_daily_rate"] == 55
    assert history["original_total"] == 165


def test_legacy_booking_without_price_snapshot_displays_no_estimate(client):
    booking = book(client)
    with Session(main.engine) as session:
        reservation = session.get(Reservation, booking["id"])
        reservation.booked_daily_rate = None
        session.add(reservation)
        session.commit()
    history = lookup(client, booking).json()
    assert history["booked_daily_rate"] is None
    assert history["original_total"] is None


def test_existing_database_migration_adds_snapshot_column_without_guessing_old_price(
    tmp_path, monkeypatch
):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'legacy_history.db'}",
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE vehicle (id INTEGER PRIMARY KEY, make VARCHAR NOT NULL, "
            "model VARCHAR NOT NULL, category VARCHAR NOT NULL, daily_rate FLOAT NOT NULL, "
            "available BOOLEAN NOT NULL)"
        ))
        connection.execute(text(
            "CREATE TABLE reservation (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL, "
            "customer_name VARCHAR NOT NULL, start_date DATE NOT NULL, end_date DATE NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO vehicle VALUES (1, 'Honda', 'Civic', 'compact', 70, 1)"
        ))
        connection.execute(text(
            "INSERT INTO reservation VALUES "
            "(1, 1, 'Old customer', '2020-01-01', '2020-01-04')"
        ))
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app):
        main.migrate_existing_database()
        with Session(engine) as session:
            old_booking = session.get(Reservation, 1)
            assert old_booking.customer_name == "Old customer"
            assert old_booking.booked_daily_rate is None
            assert old_booking.management_token_hash is None
    engine.dispose()


def test_history_lookup_does_not_change_reservation(client):
    booking = book(client)
    assert lookup(client, booking).status_code == 200
    with Session(main.engine) as session:
        reservation = session.get(Reservation, booking["id"])
        assert reservation.status == "confirmed"
