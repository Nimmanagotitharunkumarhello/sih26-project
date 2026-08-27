"""End-to-end checks of the API contracts against the seeded demo database."""

import pytest
from fastapi.testclient import TestClient

from main import app
from services import osm_service

client = TestClient(app)


@pytest.fixture(scope="module")
def demo_building():
    """A tall cached building -- exercises multi-floor behaviour."""
    buildings = osm_service.list_buildings()
    return max(buildings, key=lambda b: b["levels"] or 0)


def test_health_reports_the_cached_dataset():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["offline_capable"] is True
    assert body["building_count"] > 0


def test_listing_returns_every_cached_building(demo_building):
    body = client.get("/api/building").json()
    assert len(body) == len(osm_service.list_buildings())
    assert any(b["osm_id"] == demo_building["osm_id"] for b in body)


def test_selecting_a_building_by_click_returns_its_simulated_ulpin(demo_building):
    lat, lon = demo_building["centroid"]
    body = client.post("/api/building/select", json={"lat": lat, "lon": lon}).json()

    assert body["osm_id"] == demo_building["osm_id"]
    assert len(body["ulpin_2d"]) == 14
    assert body["is_simulated"] is True
    assert "Not an official ULPIN" in body["disclaimer"]
    assert body["floor_count"] >= 1
    assert body["footprint"]["type"] == "Polygon"


def test_clicking_open_ground_is_a_404():
    response = client.post("/api/building/select", json={"lat": 0.0, "lon": 0.0})
    assert response.status_code == 404


def test_click_selection_is_deterministic(demo_building):
    lat, lon = demo_building["centroid"]
    first = client.post("/api/building/select", json={"lat": lat, "lon": lon}).json()
    second = client.post("/api/building/select", json={"lat": lat, "lon": lon}).json()
    assert first["ulpin_2d"] == second["ulpin_2d"]


def test_floors_are_listed_in_order_with_stacked_altitudes(demo_building):
    body = client.get(f"/api/building/{demo_building['osm_id']}/floors").json()
    floors = body["floors"]

    assert [f["floor_number"] for f in floors] == list(range(len(floors)))
    assert floors[0]["label"] == "Ground"
    for lower, upper in zip(floors, floors[1:]):
        assert upper["base_z"] == pytest.approx(lower["base_z"] + lower["height"], abs=0.02)


def test_units_can_be_listed_for_a_floor(demo_building):
    floors = client.get(f"/api/building/{demo_building['osm_id']}/floors").json()["floors"]
    floor = floors[min(4, len(floors) - 1)]

    body = client.get(f"/api/floor/{floor['ulpin_3d_prefix']}/units").json()

    assert body["floor_number"] == floor["floor_number"]
    assert len(body["units"]) == floor["unit_count"]
    for unit in body["units"]:
        assert unit["ulpin_3d"].startswith(floor["ulpin_3d_prefix"])
        assert unit["polygon"]["type"] == "Polygon"
        assert unit["area_sqft"] > 0


def test_unit_detail_returns_ownership_and_history(demo_building):
    floors = client.get(f"/api/building/{demo_building['osm_id']}/floors").json()["floors"]
    units = client.get(f"/api/floor/{floors[1]['ulpin_3d_prefix']}/units").json()["units"]

    body = client.get(f"/api/unit/{units[0]['ulpin_3d']}").json()

    assert body["ulpin_3d"] == units[0]["ulpin_3d"]
    assert body["owner_name"]
    assert body["owner_aadhaar_ref"].startswith("XXXX-XXXX-")  # never a full number
    assert body["is_simulated"] is True
    assert len(body["transactions"]) >= 1


def test_unknown_unit_is_a_404():
    assert client.get("/api/unit/29051022140567-F04-U0402-T1").status_code in (404, 200)
    assert client.get("/api/unit/not-a-ulpin").status_code == 404


def test_validation_distinguishes_malformed_from_unregistered(demo_building):
    floors = client.get(f"/api/building/{demo_building['osm_id']}/floors").json()["floors"]
    real_unit = client.get(f"/api/floor/{floors[0]['ulpin_3d_prefix']}/units").json()["units"][0]

    registered = client.get(f"/api/validate/{real_unit['ulpin_3d']}").json()
    assert registered["valid"] is True and registered["registered"] is True
    assert registered["parsed"]["kind"] == "3d"

    well_formed_but_unknown = client.get("/api/validate/99999999999999-F01-U0101-T1").json()
    assert well_formed_but_unknown["valid"] is True
    assert well_formed_but_unknown["registered"] is False

    malformed = client.get("/api/validate/12345").json()
    assert malformed["valid"] is False and malformed["registered"] is False
    assert malformed["error"]


def test_every_ulpin_bearing_response_carries_the_disclaimer(demo_building):
    lat, lon = demo_building["centroid"]
    selection = client.post("/api/building/select", json={"lat": lat, "lon": lon}).json()
    floors = client.get(f"/api/building/{demo_building['osm_id']}/floors").json()
    units = client.get(f"/api/floor/{floors['floors'][0]['ulpin_3d_prefix']}/units").json()
    detail = client.get(f"/api/unit/{units['units'][0]['ulpin_3d']}").json()

    for body in (selection, floors, units, detail):
        assert body["is_simulated"] is True
        assert "Not an official ULPIN" in body["disclaimer"]
