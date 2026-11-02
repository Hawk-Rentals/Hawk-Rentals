import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import main
from models import Vehicle


@pytest.fixture
def client(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(main, "engine", test_engine)
    with TestClient(main.app) as test_client:
        yield test_client, test_engine
    test_engine.dispose()


def vehicle_payload():
    return {
        "make": "BMW", "model": "M4", "category": "Luxury",
        "daily_rate": 199.99, "available": True,
    }


def test_add_vehicle(client):
    api, _ = client
    response = api.post("/vehicles", json=vehicle_payload())
    assert response.status_code == 200
    assert response.json()["id"] > 0
    assert response.json()["archived"] is False


def test_add_vehicle_invalid_price(client):
    api, _ = client
    payload = vehicle_payload()
    payload["daily_rate"] = -1
    assert api.post("/vehicles", json=payload).status_code == 422


def test_edit_vehicle(client):
    api, _ = client
    vehicle_id = api.post("/vehicles", json=vehicle_payload()).json()["id"]
    response = api.patch(f"/vehicles/{vehicle_id}", json={"daily_rate": 225.0})
    assert response.status_code == 200
    assert response.json()["daily_rate"] == 225.0
    assert response.json()["make"] == "BMW"


def test_edit_nonexistent_vehicle(client):
    api, _ = client
    assert api.patch("/vehicles/999", json={"make": "Honda"}).status_code == 404


def test_edit_rejects_invalid_payload(client):
    api, _ = client
    vehicle_id = api.post("/vehicles", json=vehicle_payload()).json()["id"]
    assert api.patch(f"/vehicles/{vehicle_id}", json={"daily_rate": 0}).status_code == 422
    assert api.patch(f"/vehicles/{vehicle_id}", json={"archived": True}).status_code == 422


def test_archive_hides_but_preserves_vehicle(client):
    api, engine = client
    vehicle_id = api.post("/vehicles", json=vehicle_payload()).json()["id"]
    result = api.patch(f"/vehicles/{vehicle_id}/archive")
    assert result.status_code == 200
    assert result.json()["archived"] is True
    assert result.json()["available"] is False
    assert all(x["id"] != vehicle_id for x in api.get("/vehicles").json())
    with Session(engine) as session:
        assert session.get(Vehicle, vehicle_id).archived is True
    assert api.patch(f"/vehicles/{vehicle_id}", json={"make": "New"}).status_code == 404


def test_archive_missing_vehicle(client):
    api, _ = client
    assert api.patch("/vehicles/999/archive").status_code == 404


def test_archived_vehicle_cannot_be_reserved(client):
    api, _ = client
    vehicle_id = api.post("/vehicles", json=vehicle_payload()).json()["id"]
    api.patch(f"/vehicles/{vehicle_id}/archive")
    result = api.post("/reservations", json={
        "vehicle_id": vehicle_id,
        "customer_name": "Test User",
        "driver_license_number": "ABC123456",
        "driver_license_expiry": "2030-01-01",
        "start_date": "2027-01-01",
        "end_date": "2027-01-03",
    })
    assert result.status_code == 409

