from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(main, "engine", engine)
    with TestClient(main.app) as test_client:
        yield test_client
    engine.dispose()


@pytest.fixture
def dates():
    start = date.today() + timedelta(days=7)
    end = start + timedelta(days=3)
    return start, end


def booking(dates, **changes):
    start, end = dates
    data = {
        "vehicle_id": 1,
        "customer_name": "Taylor",
        "driver_license_number": "D1234567",
        "driver_license_expiry": (end + timedelta(days=365)).isoformat(),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }
    data.update(changes)
    return data


def add_vehicle(client, available=True):
    response = client.post(
        "/vehicles",
        json={
            "make": "Toyota",
            "model": "Corolla",
            "category": "compact",
            "daily_rate": 60,
            "available": available,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_creates_reservation(client, dates):
    vehicle_id = add_vehicle(client)
    response = client.post("/reservations", json=booking(dates, vehicle_id=vehicle_id))
    assert response.status_code == 201
    assert response.json()["id"] is not None
    assert response.json()["vehicle_id"] == vehicle_id
    assert "driver_license_number" not in response.json()


def test_rejects_overlapping_booking(client, dates):
    vehicle_id = add_vehicle(client)
    payload = booking(dates, vehicle_id=vehicle_id)
    assert client.post("/reservations", json=payload).status_code == 201
    assert client.post("/reservations", json=payload).status_code == 409


def test_allows_adjacent_dates(client, dates):
    vehicle_id = add_vehicle(client)
    assert client.post("/reservations", json=booking(dates, vehicle_id=vehicle_id)).status_code == 201
    _, end = dates
    next_period = booking(
        dates,
        vehicle_id=vehicle_id,
        start_date=end.isoformat(),
        end_date=(end + timedelta(days=1)).isoformat(),
    )
    assert client.post("/reservations", json=next_period).status_code == 201


@pytest.mark.parametrize("field", ["customer_name", "driver_license_number"])
def test_requires_customer_and_license(client, dates, field):
    add_vehicle(client)
    assert client.post("/reservations", json=booking(dates, **{field: "  "})).status_code == 400


def test_rejects_invalid_dates(client, dates):
    add_vehicle(client)
    start, _ = dates
    response = client.post("/reservations", json=booking(dates, end_date=start.isoformat()))
    assert response.status_code == 400


def test_rejects_expired_license(client, dates):
    add_vehicle(client)
    start, _ = dates
    response = client.post(
        "/reservations", json=booking(dates, driver_license_expiry=start.isoformat())
    )
    assert response.status_code == 400


def test_rejects_missing_or_unavailable_vehicle(client, dates):
    assert client.post("/reservations", json=booking(dates, vehicle_id=999)).status_code == 404
    vehicle_id = add_vehicle(client, available=False)
    assert client.post("/reservations", json=booking(dates, vehicle_id=vehicle_id)).status_code == 409
