"""USER-2 (Filter By Type): tests for GET /vehicles?category=...

Uses the same in-memory SQLite fixture style as test_staff_vehicle_api.py.
Assertions only look at make/model/category, so they stay valid after USER-5
adds an extra `status` field to the response.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import main


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
    with TestClient(main.app) as test_client:
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
    """Three vehicles across two categories."""
    add_vehicle(client, "Toyota", "RAV4", "SUV")
    add_vehicle(client, "Ford", "Escape", "SUV")
    add_vehicle(client, "Honda", "Civic", "Sedan")
    return client


def test_filter_returns_only_matching_category(seeded):
    response = seeded.get("/vehicles", params={"category": "SUV"})
    assert response.status_code == 200
    vehicles = response.json()
    assert len(vehicles) == 2
    assert {v["category"] for v in vehicles} == {"SUV"}


def test_no_category_returns_all_vehicles(seeded):
    vehicles = seeded.get("/vehicles").json()
    assert {v["model"] for v in vehicles} == {"RAV4", "Escape", "Civic"}


def test_empty_category_means_all_categories(seeded):
    # The dropdown's "All categories" option sends no filter.
    assert len(seeded.get("/vehicles", params={"category": ""}).json()) == 3


def test_unknown_category_returns_empty_list(seeded):
    response = seeded.get("/vehicles", params={"category": "Truck"})
    assert response.status_code == 200
    assert response.json() == []


def test_archived_vehicles_excluded_from_filtered_results(seeded):
    # Archive the Escape (STAFF-1 behaviour) and confirm it disappears from the SUV list.
    suvs = seeded.get("/vehicles", params={"category": "SUV"}).json()
    escape_id = next(v["id"] for v in suvs if v["model"] == "Escape")
    assert seeded.patch(f"/vehicles/{escape_id}/archive").status_code == 200

    remaining = seeded.get("/vehicles", params={"category": "SUV"}).json()
    assert [v["model"] for v in remaining] == ["RAV4"]


def test_category_filter_is_exact_match(seeded):
    # The dropdown is built from real category values, so exact matching is enough.
    assert seeded.get("/vehicles", params={"category": "SU"}).json() == []