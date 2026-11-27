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
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
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
        headers={"X-Staff-Key": "test-staff-key"},
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


def test_edit_keeps_booking_identity_and_releases_original_vehicle(client, dates):
    original = booking(dates)
    created = client.post("/reservations", json=original).json()
    path = f"/reservations/{created['id']}"
    headers = {"X-Booking-Token": created["management_token"]}
    _, end = dates
    updated = {**original, "end_date": (end + timedelta(days=2)).isoformat()}
    assert client.patch(
        "/vehicles/1", headers={"X-Staff-Key": "test-staff-key"}, json={"daily_rate": 75}
    ).status_code == 200

    # A date extension can overlap the reservation being edited.
    assert client.put(path, headers=headers, json=updated).status_code == 200
    assert client.get(f"{path}/history", headers=headers).json()["original_total"] == 275

    updated.update(vehicle_id=2, customer_name="  Taylor Morgan  ")
    response = client.put(path, headers=headers, json=updated)
    assert response.status_code == 200
    assert response.json() == {
        "id": created["id"], "status": "confirmed", "vehicle_id": 2,
        "customer_name": "Taylor Morgan", "start_date": updated["start_date"],
        "end_date": updated["end_date"],
    }
    assert client.get(path, headers=headers).json() == response.json()
    assert client.get(f"{path}/history", headers=headers).json()["original_total"] == 300
    assert client.post("/reservations", json=original).status_code == 201
    assert client.post("/reservations", json=updated).status_code == 409


def test_rejected_edits_preserve_original_booking(client, dates):
    original = booking(dates)
    created = client.post("/reservations", json=original).json()
    path = f"/reservations/{created['id']}"
    headers = {"X-Booking-Token": created["management_token"]}
    saved = client.get(path, headers=headers).json()
    conflict = {**original, "vehicle_id": 2}
    other = client.post("/reservations", json=conflict).json()
    wrong_headers = {"X-Booking-Token": other["management_token"]}

    assert client.put(path, headers=wrong_headers, json=conflict).status_code == 404
    assert client.put(path, headers=headers, json=conflict).status_code == 409
    for change in (
        {"start_date": original["end_date"]},
        {"start_date": date.today().isoformat()},
        {"driver_license_expiry": original["start_date"]},
    ):
        assert client.put(path, headers=headers, json={**original, **change}).status_code == 400
    assert client.get(path, headers=headers).json() == saved

    assert client.post(f"{path}/cancel", headers=headers).status_code == 200
    assert client.put(path, headers=headers, json=original).status_code == 409


def test_booking_that_has_started_cannot_be_moved(client, dates):
    upcoming = booking(dates)
    started = {**upcoming, "start_date": date.today().isoformat()}
    created = client.post("/reservations", json=started).json()
    headers = {"X-Booking-Token": created["management_token"]}
    assert client.put(f"/reservations/{created['id']}", headers=headers, json=upcoming).status_code == 409


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
