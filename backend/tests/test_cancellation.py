from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, create_engine

import main
from models import Reservation


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'cancellation.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as client:
        yield client
    engine.dispose()


def book(client, offset=7, vehicle_id=1):
    start = date.today() + timedelta(days=offset)
    payload = {
        "vehicle_id": vehicle_id,
        "customer_name": "Nicholas",
        "driver_license_number": "D1234567",
        "driver_license_expiry": (start + timedelta(days=365)).isoformat(),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=3)).isoformat(),
    }
    response = client.post("/reservations", json=payload)
    assert response.status_code == 201
    return response.json(), payload


def credentials(booking):
    return {"X-Booking-Token": booking["management_token"]}


def test_customer_can_lookup_and_cancel_without_deleting_history(client):
    booking, _ = book(client)
    path = f"/reservations/{booking['id']}"
    headers = credentials(booking)
    found = client.get(path, headers=headers)
    assert found.status_code == 200
    assert found.json()["status"] == "confirmed"
    assert "management_token" not in found.json()
    assert "management_token_hash" not in found.json()
    assert "management_token_hash" not in booking
    response = client.post(f"{path}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert "management_token_hash" not in response.json()
    assert client.get(path, headers=headers).json()["status"] == "cancelled"
    with Session(main.engine) as session:
        saved = session.get(Reservation, booking["id"])
        assert saved.status == "cancelled"
        assert saved.management_token_hash != booking["management_token"]


@pytest.mark.parametrize("method,suffix", [("get", ""), ("post", "/cancel")])
@pytest.mark.parametrize("token", [None, "incorrect"])
def test_booking_credentials_required(client, method, suffix, token):
    booking, _ = book(client)
    response = getattr(client, method)(
        f"/reservations/{booking['id']}{suffix}",
        headers={} if token is None else {"X-Booking-Token": token},
    )
    assert response.status_code == 404
    assert "customer_name" not in response.json()
    assert client.get(f"/reservations/{booking['id']}", headers=credentials(booking)).json()["status"] == "confirmed"


def test_code_for_another_booking_cannot_cancel(client):
    first, _ = book(client)
    second, _ = book(client, vehicle_id=2)
    assert client.post(f"/reservations/{first['id']}/cancel", headers=credentials(second)).status_code == 404


def test_missing_booking_returns_helpful_error(client):
    response = client.post("/reservations/99999/cancel", headers={"X-Booking-Token": "unknown"})
    assert response.status_code == 404
    assert "access code" in response.json()["detail"]


def test_repeated_cancellation_is_rejected(client):
    booking, _ = book(client)
    path = f"/reservations/{booking['id']}/cancel"
    assert client.post(path, headers=credentials(booking)).status_code == 200
    response = client.post(path, headers=credentials(booking))
    assert response.status_code == 409
    assert "already been cancelled" in response.json()["detail"]


@pytest.mark.parametrize("offset", [-5, 0])
def test_started_or_past_reservation_cannot_be_cancelled(client, offset):
    booking, _ = book(client, offset=offset)
    response = client.post(f"/reservations/{booking['id']}/cancel", headers=credentials(booking))
    assert response.status_code == 409
    assert client.get(f"/reservations/{booking['id']}", headers=credentials(booking)).json()["status"] == "confirmed"


def test_cancellation_releases_dates_and_allows_rebooking(client):
    booking, payload = book(client)
    params = {key: payload[key] for key in ("start_date", "end_date")}
    params["status"] = "available"
    assert booking["vehicle_id"] not in [v["id"] for v in client.get("/vehicles", params=params).json()]
    assert client.post("/reservations", json=payload).status_code == 409
    assert client.post(f"/reservations/{booking['id']}/cancel", headers=credentials(booking)).status_code == 200
    assert booking["vehicle_id"] in [v["id"] for v in client.get("/vehicles", params=params).json()]
    assert client.post("/reservations", json=payload).status_code == 201
    assert booking["vehicle_id"] not in [v["id"] for v in client.get("/vehicles", params=params).json()]


def test_cancelling_does_not_override_out_of_service_vehicle(client):
    booking, payload = book(client)
    with main.engine.begin() as connection:
        connection.execute(text("UPDATE vehicle SET available = 0 WHERE id = 1"))
    assert client.post(f"/reservations/{booking['id']}/cancel", headers=credentials(booking)).status_code == 200
    vehicles = client.get("/vehicles", params={"start_date": payload["start_date"], "end_date": payload["end_date"]}).json()
    assert next(v for v in vehicles if v["id"] == 1)["status"] == "unavailable"


def test_existing_database_is_migrated_without_losing_bookings(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE vehicle (id INTEGER PRIMARY KEY, make VARCHAR NOT NULL, model VARCHAR NOT NULL, category VARCHAR NOT NULL, daily_rate FLOAT NOT NULL, available BOOLEAN NOT NULL)"))
        connection.execute(text("CREATE TABLE reservation (id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL, customer_name VARCHAR NOT NULL, start_date DATE NOT NULL, end_date DATE NOT NULL)"))
        connection.execute(text("INSERT INTO vehicle VALUES (1, 'Toyota', 'Corolla', 'compact', 55, 1)"))
        connection.execute(text("INSERT INTO reservation VALUES (1, 1, 'Existing customer', '2099-01-01', '2099-01-04')"))
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as client:
        main.migrate_existing_database()  # Repeated startups are safe.
        with Session(engine) as session:
            reservation = session.get(Reservation, 1)
            assert reservation.customer_name == "Existing customer"
            assert reservation.status == "confirmed"
            assert reservation.management_token_hash is None
        assert client.get("/vehicles", params={"start_date": "2099-01-01", "end_date": "2099-01-04"}).json()[0]["status"] == "booked"
        assert client.post("/reservations/1/cancel").status_code == 404
    engine.dispose()
