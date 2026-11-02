"""USER-2 (Filter By Type): tests for GET /vehicles?category=...

Uses the same in-memory SQLite fixture style as the other test files. The app seeds a
starter fleet when the database is empty (STAFF-1), so these tests use their own
category names ("Test-SUV", "Test-Sedan") and compare against a baseline count instead
of assuming the database holds only the vehicles created here.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import main

SUV = "Test-SUV"
SEDAN = "Test-Sedan"


@pytest.fixture
def client(monkeypatch):
    # Fresh in-memory database for every test, swapped in for the real engine.
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(main, "engine", test_engine)
    # Adding and archiving vehicles are staff-only endpoints (STAFF-1), so the tests
    # set a staff key and send it as the X-Staff-Key header on every request.
    # GET /vehicles is public, so the extra header does not affect the filter tests.
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
    with TestClient(main.app, headers={"X-Staff-Key": "test-staff-key"}) as test_client:
        yield test_client
    test_engine.dispose()


def add_vehicle(api, make, model, category, rate=50.0):
    """Create a vehicle through the API and return its id."""
    response = api.post(
        "/vehicles",
        json={"make": make, "model": model, "category": category, "daily_rate": rate},
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture
def seeded(client):
    """Adds three vehicles in two categories. `client.baseline` is how many existed before."""
    client.baseline = len(client.get("/vehicles").json())
    add_vehicle(client, "Toyota", "RAV4", SUV)
    add_vehicle(client, "Ford", "Escape", SUV)
    add_vehicle(client, "Honda", "Civic", SEDAN)
    return client


def test_filter_returns_only_matching_category(seeded):
    response = seeded.get("/vehicles", params={"category": SUV})
    assert response.status_code == 200
    vehicles = response.json()
    assert {v["model"] for v in vehicles} == {"RAV4", "Escape"}
    assert {v["category"] for v in vehicles} == {SUV}


def test_no_category_returns_all_vehicles(seeded):
    vehicles = seeded.get("/vehicles").json()
    # Everything that existed before, plus the three vehicles added by the fixture.
    assert len(vehicles) == seeded.baseline + 3
    assert {"RAV4", "Escape", "Civic"} <= {v["model"] for v in vehicles}


def test_empty_category_means_all_categories(seeded):
    # The dropdown's "All categories" option sends no filter.
    vehicles = seeded.get("/vehicles", params={"category": ""}).json()
    assert len(vehicles) == seeded.baseline + 3


def test_unknown_category_returns_empty_list(seeded):
    response = seeded.get("/vehicles", params={"category": "Test-Truck"})
    assert response.status_code == 200
    assert response.json() == []


def test_archived_vehicles_excluded_from_filtered_results(seeded):
    # Archive the Escape (STAFF-1 behaviour) and confirm it disappears from the SUV list.
    suvs = seeded.get("/vehicles", params={"category": SUV}).json()
    escape_id = next(v["id"] for v in suvs if v["model"] == "Escape")
    assert seeded.patch(f"/vehicles/{escape_id}/archive").status_code == 200

    remaining = seeded.get("/vehicles", params={"category": SUV}).json()
    assert [v["model"] for v in remaining] == ["RAV4"]


def test_category_filter_is_exact_match(seeded):
    # The dropdown is built from real category values, so exact matching is enough.
    assert seeded.get("/vehicles", params={"category": "Test-SU"}).json() == []