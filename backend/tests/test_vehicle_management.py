import pytest
from fastapi.testclient import TestClient
from sqlmodel import create_engine

import main
from models import Vehicle


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'vehicles.db'}", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
    with TestClient(main.app) as test_client:
        yield test_client
    engine.dispose()


def staff_headers():
    return {"X-Staff-Key": "test-staff-key"}


def test_initial_fleet_is_seeded_once_and_visible_in_catalog(client):
    vehicles = client.get("/vehicles").json()
    assert len(vehicles) >= 4
    assert {vehicle["make"] for vehicle in vehicles} >= {"Toyota", "Honda", "Ford"}


def test_staff_credentials_required_for_vehicle_changes(client):
    payload = {"make": "Mazda", "model": "3", "category": "compact", "daily_rate": 58}
    assert client.post("/vehicles", json=payload).status_code == 401
    vehicle_id = client.get("/vehicles").json()[0]["id"]
    assert client.patch(f"/vehicles/{vehicle_id}", json={"daily_rate": 70}).status_code == 401
    assert client.patch(f"/vehicles/{vehicle_id}/archive").status_code == 401


def test_staff_can_create_and_update_vehicle_and_catalog_reflects_changes(client):
    payload = {"make": "Mazda", "model": "3", "category": "compact", "daily_rate": 58}
    created = client.post("/vehicles", headers=staff_headers(), json=payload)
    assert created.status_code == 200
    vehicle_id = created.json()["id"]

    updated = client.patch(
        f"/vehicles/{vehicle_id}",
        headers=staff_headers(),
        json={"daily_rate": 65, "available": False},
    )
    assert updated.status_code == 200
    assert updated.json()["daily_rate"] == 65
    catalog_item = next(item for item in client.get("/vehicles").json() if item["id"] == vehicle_id)
    assert catalog_item["daily_rate"] == 65
    assert catalog_item["available"] is False


def test_archiving_hides_vehicle_from_catalog_but_keeps_database_record(client):
    vehicle_id = client.get("/vehicles").json()[0]["id"]
    response = client.patch(f"/vehicles/{vehicle_id}/archive", headers=staff_headers())
    assert response.status_code == 200
    assert response.json()["archived"] is True
    assert all(item["id"] != vehicle_id for item in client.get("/vehicles").json())

    with main.Session(main.engine) as session:
        archived = session.get(Vehicle, vehicle_id)
        assert archived is not None
        assert archived.archived is True


def test_invalid_vehicle_data_is_rejected(client):
    response = client.post(
        "/vehicles",
        headers=staff_headers(),
        json={"make": " ", "model": "3", "category": "compact", "daily_rate": -1},
    )
    assert response.status_code == 422
