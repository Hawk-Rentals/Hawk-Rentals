"""USER-4 (Filter By Price): tests for GET /vehicles?min_price=...&max_price=...

Same fixture style as test_category_filter.py. The app seeds a starter fleet when the
database is empty, so every test uses its own category name ("Price-Test") and only
looks at vehicles in that category. That keeps the tests independent of the seed data
and also exercises the price filter combined with the category filter (USER-2).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import main

CATEGORY = "Price-Test"


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
    # Creating vehicles is staff-only (STAFF-1); GET /vehicles itself is public.
    monkeypatch.setenv("STAFF_API_KEY", "test-staff-key")
    with TestClient(main.app, headers={"X-Staff-Key": "test-staff-key"}) as test_client:
        yield test_client
    test_engine.dispose()


def add_vehicle(api, model, rate, category=CATEGORY):
    response = api.post(
        "/vehicles",
        json={"make": "Test", "model": model, "category": category, "daily_rate": rate},
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture
def priced(client):
    """Three vehicles at $40, $75 and $120 per day."""
    add_vehicle(client, "Cheap", 40)
    add_vehicle(client, "Mid", 75)
    add_vehicle(client, "Pricey", 120)
    return client


def models(api, **params):
    """Models returned for the test category with the given extra filters."""
    response = api.get("/vehicles", params={"category": CATEGORY, **params})
    assert response.status_code == 200
    return {v["model"] for v in response.json()}


def test_min_price_only(priced):
    assert models(priced, min_price=75) == {"Mid", "Pricey"}


def test_max_price_only(priced):
    assert models(priced, max_price=75) == {"Cheap", "Mid"}


def test_min_and_max_price_range(priced):
    assert models(priced, min_price=50, max_price=100) == {"Mid"}


def test_range_is_inclusive_on_both_ends(priced):
    # Exactly $40 and exactly $120 must be included.
    assert models(priced, min_price=40, max_price=120) == {"Cheap", "Mid", "Pricey"}


def test_no_price_params_returns_everything(priced):
    assert models(priced) == {"Cheap", "Mid", "Pricey"}


def test_no_match_returns_empty_list(priced):
    assert models(priced, min_price=500) == set()


def test_min_greater_than_max_is_rejected(priced):
    response = priced.get("/vehicles", params={"min_price": 100, "max_price": 50})
    assert response.status_code == 400


def test_negative_price_is_rejected(priced):
    assert priced.get("/vehicles", params={"min_price": -5}).status_code == 422


def test_non_numeric_price_is_rejected(priced):
    assert priced.get("/vehicles", params={"max_price": "cheap"}).status_code == 422


def test_price_combines_with_category(priced):
    # Another category with a price inside the range must NOT leak into the results.
    add_vehicle(priced, "OtherCategory", 75, category="Price-Other")
    assert models(priced, min_price=50, max_price=100) == {"Mid"}


def test_price_combines_with_availability_status(priced):
    # USER-5's status filter still works together with the price range.
    mid_id = next(
        v["id"] for v in priced.get("/vehicles", params={"category": CATEGORY}).json()
        if v["model"] == "Mid"
    )
    assert priced.patch(f"/vehicles/{mid_id}", json={"available": False}).status_code == 200
    assert models(priced, min_price=50, max_price=100, status="unavailable") == {"Mid"}
    assert models(priced, min_price=50, max_price=100, status="available") == set()


def test_archived_vehicles_excluded_from_price_results(priced):
    mid_id = next(
        v["id"] for v in priced.get("/vehicles", params={"category": CATEGORY}).json()
        if v["model"] == "Mid"
    )
    assert priced.patch(f"/vehicles/{mid_id}/archive").status_code == 200
    assert models(priced, min_price=50, max_price=100) == set()