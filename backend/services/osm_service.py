"""Serve building footprints from the pre-fetched local dataset.

Deliberately offline. `scripts/prefetch_osm.py` is what talks to Overpass; this
module only reads the GeoJSON that script committed, so a request never depends
on an external API being reachable.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_city" / "buildings.geojson"

#: How far outside a footprint a click still counts as selecting it. Roughly
#: 30m -- forgiving enough for a fingertip on a phone, tight enough that two
#: neighbouring buildings do not both match.
CLICK_TOLERANCE_DEG = 0.00027


class BuildingNotFound(LookupError):
    """Raised when no cached building matches the query."""


@lru_cache(maxsize=1)
def _dataset() -> dict:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Demo dataset missing at {DATASET_PATH}. "
            "Run: python scripts/prefetch_osm.py"
        )
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _index() -> tuple[list[dict], list, STRtree]:
    """Build an R-tree over the footprints so click lookup stays O(log n)."""
    features = _dataset()["features"]
    geometries = [shape(feature["geometry"]) for feature in features]
    return features, geometries, STRtree(geometries)


def _properties(feature: dict, geometry) -> dict:
    props = feature["properties"]
    centroid = geometry.centroid
    return {
        "osm_id": props["osm_id"],
        "name": props.get("name"),
        "address": props.get("address"),
        "building_type": props.get("building_type"),
        "levels": props.get("levels"),
        "height": props.get("height"),
        "footprint": feature["geometry"],
        "centroid": [centroid.y, centroid.x],  # [lat, lon]
    }


def list_buildings() -> list[dict]:
    """Every cached building, for the 2D map's overlay layer."""
    features, geometries, _ = _index()
    return [_properties(f, g) for f, g in zip(features, geometries)]


def get_building(osm_id: str) -> dict:
    features, geometries, _ = _index()
    for feature, geometry in zip(features, geometries):
        if feature["properties"]["osm_id"] == osm_id:
            return _properties(feature, geometry)
    raise BuildingNotFound(f"no cached building with osm_id {osm_id!r}")


def find_building_at(lat: float, lon: float) -> dict:
    """Resolve a map click to a building.

    Prefers a footprint the point actually falls inside; otherwise takes the
    nearest one within the click tolerance.
    """
    features, geometries, tree = _index()
    point = Point(lon, lat)

    for index in tree.query(point):
        if geometries[index].covers(point):
            return _properties(features[index], geometries[index])

    nearest = tree.nearest(point)
    if nearest is not None:
        index = int(nearest)
        if geometries[index].distance(point) <= CLICK_TOLERANCE_DEG:
            return _properties(features[index], geometries[index])

    raise BuildingNotFound(f"no cached building near ({lat}, {lon})")


def dataset_metadata() -> dict:
    return _dataset().get("metadata", {})
