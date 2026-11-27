from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, select

import main
from models import Vehicle
from vehicle_maintenance import VehicleMaintenance


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'maintenance.db'}",
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setenv("STAFF_API_KEY", "rep2b-secret")
    with TestClient(main.app) as test_client:
        yield test_client
    engine.dispose()


def headers():
    return {"X-Staff-Key": "rep2b-secret"}


def vehicles(client):
    return client.get("/staff/maintenance/vehicles", headers=headers()).json()


def add(client, vehicle_id, kind="maintenance", description="Oil and filter changed"):
    return client.post(
        f"/staff/vehicles/{vehicle_id}/maintenance",
        headers=headers(),
        json={"entry_type": kind, "description": description,
              "service_date": date.today().isoformat()},
    )


def test_staff_credentials_required_for_every_endpoint(client):
    vid = client.get("/vehicles").json()[0]["id"]
    assert client.get("/staff/maintenance/vehicles").status_code == 401
    assert client.get(f"/staff/vehicles/{vid}/maintenance").status_code == 401
    assert client.post(f"/staff/vehicles/{vid}/maintenance", json={
        "entry_type": "defect", "description": "Brake wear"
    }).status_code == 401
    assert client.patch(
        f"/staff/vehicles/{vid}/maintenance/1/resolve",
        json={"resolution_notes": "Fixed brakes"},
    ).status_code == 401
    assert client.get("/staff/maintenance/vehicles", headers={"X-Staff-Key": "bad"}).status_code == 401


def test_staff_can_log_and_view_maintenance_in_date_order(client):
    vid = vehicles(client)[0]["id"]
    response = add(client, vid)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["status"] == "completed"
    assert record["entry_type"] == "maintenance"
    assert record["service_date"] == date.today().isoformat()
    assert record["resolved_at"] is None
    assert record["resolution_notes"] is None
    history = client.get(f"/staff/vehicles/{vid}/maintenance", headers=headers())
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [record["id"]]


def test_open_defect_can_be_resolved_with_audit_notes(client):
    vid = vehicles(client)[0]["id"]
    defect = add(client, vid, "defect", "Oil leak").json()
    assert defect["status"] == "open"
    response = client.patch(
        f"/staff/vehicles/{vid}/maintenance/{defect['id']}/resolve",
        headers=headers(),
        json={"resolution_notes": "Oil seal replaced"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "resolved"
    assert result["resolution_notes"] == "Oil seal replaced"
    assert result["resolved_at"] is not None
    refreshed = client.get(f"/staff/vehicles/{vid}/maintenance", headers=headers()).json()
    assert refreshed[0]["status"] == "resolved"
    assert refreshed[0]["resolution_notes"] == "Oil seal replaced"


def test_resolution_cannot_be_repeated(client):
    vid = vehicles(client)[0]["id"]
    defect = add(client, vid, "defect", "Door latch").json()
    path = f"/staff/vehicles/{vid}/maintenance/{defect['id']}/resolve"
    payload = {"resolution_notes": "Latch repaired"}
    assert client.patch(path, headers=headers(), json=payload).status_code == 200
    assert client.patch(path, headers=headers(), json=payload).status_code == 409


def test_completed_maintenance_cannot_be_resolved_as_defect(client):
    vid = vehicles(client)[0]["id"]
    record = add(client, vid).json()
    assert client.patch(
        f"/staff/vehicles/{vid}/maintenance/{record['id']}/resolve",
        headers=headers(), json={"resolution_notes": "Not a defect"},
    ).status_code == 409


@pytest.mark.parametrize("payload", [
    {"entry_type": "defect", "description": "  "},
    {"entry_type": "repair", "description": "New brake pads"},
    {"entry_type": "maintenance", "description": "x"},
    {"entry_type": "maintenance", "description": "Good work", "unknown": True},
])
def test_invalid_maintenance_rejected(client, payload):
    vid = vehicles(client)[0]["id"]
    assert client.post(
        f"/staff/vehicles/{vid}/maintenance",
        headers=headers(), json=payload,
    ).status_code == 422


@pytest.mark.parametrize("notes", ["", " ", "x"])
def test_empty_resolution_notes_rejected(client, notes):
    vid = vehicles(client)[0]["id"]
    defect = add(client, vid, "defect", "Mirror broken").json()
    assert client.patch(
        f"/staff/vehicles/{vid}/maintenance/{defect['id']}/resolve",
        headers=headers(), json={"resolution_notes": notes},
    ).status_code == 422


def test_records_are_separated_by_vehicle(client):
    fleet = vehicles(client)
    first, second = fleet[0]["id"], fleet[1]["id"]
    record = add(client, first, "defect", "Damaged tire").json()
    assert client.get(f"/staff/vehicles/{second}/maintenance", headers=headers()).json() == []
    assert client.patch(
        f"/staff/vehicles/{second}/maintenance/{record['id']}/resolve",
        headers=headers(), json={"resolution_notes": "No action"},
    ).status_code == 404


def test_unknown_vehicle_and_record_return_not_found(client):
    assert client.get("/staff/vehicles/999999/maintenance", headers=headers()).status_code == 404
    assert client.post("/staff/vehicles/999999/maintenance", headers=headers(), json={
        "entry_type": "defect", "description": "Defective battery",
    }).status_code == 404
    vid = vehicles(client)[0]["id"]
    assert client.patch(
        f"/staff/vehicles/{vid}/maintenance/999999/resolve",
        headers=headers(), json={"resolution_notes": "Repaired"},
    ).status_code == 404


def test_archived_vehicle_history_persists(client):
    vid = vehicles(client)[0]["id"]
    recorded = add(client, vid, "defect", "Paint scratches").json()
    assert client.patch(f"/vehicles/{vid}/archive", headers=headers()).status_code == 200
    fleet = vehicles(client)
    assert next(row for row in fleet if row["id"] == vid)["archived"] is True
    history = client.get(f"/staff/vehicles/{vid}/maintenance", headers=headers())
    assert history.json()[0]["id"] == recorded["id"]


def test_maintenance_does_not_modify_vehicle_availability(client):
    vid = vehicles(client)[0]["id"]
    before = client.get("/vehicles").json()
    add(client, vid, "defect", "Engine warning light")
    after = client.get("/vehicles").json()
    assert after == before


def test_history_persists_after_api_restarts(client):
    vid = vehicles(client)[0]["id"]
    add(client, vid)
    with Session(main.engine) as session:
        records = session.exec(select(VehicleMaintenance)).all()
        assert len(records) == 1
        assert records[0].vehicle_id == vid
