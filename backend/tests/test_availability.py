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


def add_vehicle(client, model="Corolla", category="compact", available=True):
    response = client.post(
        "/vehicles",
        json={
            "make": "Toyota",
            "model": model,
            "category": category,
            "daily_rate": 60,
            "available": available,
        },
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


def search(client, start=None, end=None, **params):
    if start is not None:
        params["start_date"] = start.isoformat()
    if end is not None:
        params["end_date"] = end.isoformat()
    return client.get("/vehicles", params=params)


def statuses(response):
    assert response.status_code == 200
    return {vehicle["id"]: vehicle["status"] for vehicle in response.json()}


@pytest.fixture
def fleet(client, dates):
    start, end = dates
    free = add_vehicle(client, model="Corolla")
    booked = add_vehicle(client, model="Camry")
    out_of_service = add_vehicle(client, model="RAV4", category="suv", available=False)
    reserve(client, booked, start, end)
    return {"free": free, "booked": booked, "out_of_service": out_of_service}


def test_reports_status_of_every_vehicle_for_dates(client, dates, fleet):
    start, end = dates
    assert statuses(search(client, start, end)) == {
        fleet["free"]: "available",
        fleet["booked"]: "booked",
        fleet["out_of_service"]: "unavailable",
    }


@pytest.mark.parametrize("status", ["available", "booked", "unavailable"])
def test_filters_by_status(client, dates, fleet, status):
    start, end = dates
    expected = {"available": "free", "booked": "booked", "unavailable": "out_of_service"}
    assert list(statuses(search(client, start, end, status=status))) == [fleet[expected[status]]]


def test_booked_vehicle_is_available_outside_reservation(client, dates, fleet):
    _, end = dates
    later = statuses(search(client, end, end + timedelta(days=2)))
    assert later[fleet["booked"]] == "available"


def test_partial_overlap_counts_as_booked(client, dates, fleet):
    start, _ = dates
    overlapping = statuses(search(client, start - timedelta(days=2), start + timedelta(days=1)))
    assert overlapping[fleet["booked"]] == "booked"


def test_defaults_to_today_without_dates(client, fleet):
    today_vehicle = add_vehicle(client, model="Prius")
    reserve(client, today_vehicle, date.today(), date.today() + timedelta(days=2))
    result = statuses(search(client))
    assert result[today_vehicle] == "booked"
    assert result[fleet["booked"]] == "available"


def test_combines_status_and_category_filters(client, dates, fleet):
    start, end = dates
    assert statuses(search(client, start, end, status="available", category="suv")) == {}
    assert list(statuses(search(client, start, end, status="available", category="compact"))) == [
        fleet["free"]
    ]


def test_booking_from_filter_results_removes_vehicle(client, dates, fleet):
    start, end = dates
    reserve(client, fleet["free"], start, end)
    assert statuses(search(client, start, end, status="available")) == {}


def test_rejects_only_one_date(client, dates):
    start, _ = dates
    assert search(client, start=start).status_code == 400


def test_rejects_return_before_pickup(client, dates):
    start, end = dates
    assert search(client, end, start).status_code == 400
    assert search(client, start, start).status_code == 400


def test_rejects_unknown_status(client, dates):
    start, end = dates
    assert search(client, start, end, status="rented").status_code == 422
