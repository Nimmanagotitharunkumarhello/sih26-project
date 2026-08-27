"""Fetch the demo city's building footprints from OSM, once, ahead of time.

This is the ONLY code in the project that talks to the Overpass API, and it is
never called at request time. Run it during development; commit the GeoJSON it
writes. The running app -- and the demo -- then works with the network unplugged.

    python scripts/prefetch_osm.py

Re-run with --bbox / --limit to curate a different demo area.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "demo_city"
OUTPUT_PATH = DATA_DIR / "buildings.geojson"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

#: Overpass rejects the default requests user-agent with HTTP 406.
HEADERS = {"User-Agent": "ULPIN3D-prototype/1.0 (SIH student project)"}

#: Central Bengaluru (south, west, north, east) -- inside the Bengaluru North
#: entry of data/admin_regions.json so every building resolves to real codes.
DEFAULT_BBOX = (12.9600, 77.5800, 13.0000, 77.6400)
DEFAULT_LIMIT = 50

QUERY_TEMPLATE = """
[out:json][timeout:90];
(
  way["building"]["building:levels"]({south},{west},{north},{east});
  way["building"]["height"]({south},{west},{north},{east});
);
out geom;
"""


def _parse_levels(tags: dict) -> int | None:
    raw = tags.get("building:levels")
    try:
        levels = int(float(raw))
    except (TypeError, ValueError):
        return None
    return levels if 1 <= levels <= 99 else None


def _parse_height(tags: dict) -> float | None:
    raw = tags.get("height")
    if raw is None:
        return None
    # OSM heights are usually bare metres but occasionally carry a unit.
    cleaned = str(raw).strip().lower().removesuffix("m").strip()
    try:
        height = float(cleaned)
    except ValueError:
        return None
    return height if 0 < height <= 400 else None


def _classify(tags: dict) -> str:
    building = (tags.get("building") or "yes").lower()
    if building in ("apartments", "residential", "house", "dormitory"):
        return "residential"
    if building in ("commercial", "office", "retail", "supermarket", "hotel"):
        return "commercial"
    return "mixed"


def _to_feature(element: dict) -> dict | None:
    geometry = element.get("geometry") or []
    if len(geometry) < 4:
        return None

    ring = [[point["lon"], point["lat"]] for point in geometry]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    if len(ring) < 4:
        return None

    tags = element.get("tags") or {}
    levels = _parse_levels(tags)
    height = _parse_height(tags)
    if levels is None and height is None:
        return None

    return {
        "type": "Feature",
        "properties": {
            "osm_id": f"way/{element['id']}",
            "name": tags.get("name") or tags.get("addr:housename"),
            "building_type": _classify(tags),
            "levels": levels,
            "height": height,
            "address": ", ".join(
                part
                for part in (tags.get("addr:housenumber"), tags.get("addr:street"))
                if part
            )
            or None,
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def fetch(bbox: tuple[float, float, float, float], limit: int) -> dict:
    south, west, north, east = bbox
    query = QUERY_TEMPLATE.format(south=south, west=west, north=north, east=east)

    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying {endpoint} ...")
            response = requests.post(endpoint, data={"data": query}, headers=HEADERS, timeout=120)
            response.raise_for_status()
            payload = response.json()
            break
        except Exception as exc:  # noqa: BLE001 -- mirror-fallback is the point
            print(f"  failed: {exc}")
            last_error = exc
    else:
        raise SystemExit(f"All Overpass mirrors failed. Last error: {last_error}")

    features = [f for f in map(_to_feature, payload.get("elements", [])) if f]

    # Prefer taller buildings -- they make the exploded floor view legible.
    features.sort(
        key=lambda f: (f["properties"]["levels"] or 0, f["properties"]["height"] or 0),
        reverse=True,
    )
    features = features[:limit]
    features.sort(key=lambda f: f["properties"]["osm_id"])  # stable, diff-friendly

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "OpenStreetMap contributors (ODbL), via Overpass API",
            "bbox": list(bbox),
            "feature_count": len(features),
            "note": "Pre-fetched demo dataset. The running app reads this file "
                    "instead of calling Overpass, so the demo works offline.",
        },
        "features": features,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("S", "W", "N", "E"), default=DEFAULT_BBOX)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    collection = fetch(tuple(args.bbox), args.limit)
    if not collection["features"]:
        print("No usable buildings found -- widen the bbox and retry.")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(collection, indent=1), encoding="utf-8")

    with_levels = sum(1 for f in collection["features"] if f["properties"]["levels"])
    print(f"\nWrote {len(collection['features'])} buildings to {OUTPUT_PATH}")
    print(f"  {with_levels} have an explicit building:levels tag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
