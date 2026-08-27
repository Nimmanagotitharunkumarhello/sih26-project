"""Slice a 2D building footprint into per-floor volumes and per-unit polygons.

OSM gives us an outline and (sometimes) a height or level count. It does not
give us interior layouts, so unit boundaries here are *synthesised*: the
footprint is cut into a small grid, each cell clipped back to the outline. The
result is geometrically consistent -- units tile their floor exactly, with no
gaps or overlaps -- which is what the 3D viewer and the ULPIN scheme need.

All grid maths happen in a local metre-space projection centred on the
building, so areas and cell sizes are in real units rather than degrees.
"""

from __future__ import annotations

import math

from shapely.geometry import Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

#: Assumed storey height when OSM gives a height but no level count.
DEFAULT_FLOOR_HEIGHT_M = 3.5
#: Used when OSM gives neither height nor levels. The curated demo dataset is
#: filtered so this rarely fires.
DEFAULT_LEVELS = 4

TARGET_UNIT_AREA_SQM = 80.0
#: Capped for demo legibility -- more than six units per floor is unreadable in
#: the exploded 3D view.
MAX_UNITS_PER_FLOOR = 6
#: Clipped cells smaller than this are merged into a neighbour rather than
#: becoming their own (unsellable) unit.
MIN_UNIT_AREA_SQM = 15.0

SQM_TO_SQFT = 10.7639

_EARTH_M_PER_DEG_LAT = 110540.0
_EARTH_M_PER_DEG_LON = 111320.0


class SegmentationError(ValueError):
    """Raised when a footprint cannot be segmented."""


def infer_levels(height: float | None, levels: int | None) -> int:
    """Decide how many storeys a building has from sparse OSM tags."""
    if levels is not None and levels > 0:
        return int(levels)
    if height is not None and height > 0:
        return max(1, round(height / DEFAULT_FLOOR_HEIGHT_M))
    return DEFAULT_LEVELS


def infer_height(height: float | None, levels: int) -> float:
    """Decide total building height, falling back to levels x storey height."""
    if height is not None and height > 0:
        return float(height)
    return levels * DEFAULT_FLOOR_HEIGHT_M


def _projection(lat0: float, lon0: float):
    """Equirectangular projection about (lat0, lon0). Accurate enough over the
    tens of metres a single building spans."""
    lon_scale = _EARTH_M_PER_DEG_LON * math.cos(math.radians(lat0))

    def to_metres(lon: float, lat: float) -> tuple[float, float]:
        return ((lon - lon0) * lon_scale, (lat - lat0) * _EARTH_M_PER_DEG_LAT)

    def to_lonlat(x: float, y: float) -> tuple[float, float]:
        return (x / lon_scale + lon0, y / _EARTH_M_PER_DEG_LAT + lat0)

    return to_metres, to_lonlat


def _map_polygon(polygon: Polygon, fn) -> Polygon:
    exterior = [fn(x, y) for x, y in polygon.exterior.coords]
    interiors = [[fn(x, y) for x, y in ring.coords] for ring in polygon.interiors]
    return Polygon(exterior, interiors)


def _polygon_parts(geom: BaseGeometry) -> list[Polygon]:
    """Extract the polygonal pieces of a clip result, discarding dangling edges.

    Clipping a cell against a concave outline can return a MultiPolygon (the
    cell is split in two) or a GeometryCollection (a polygon plus a LineString
    where the cell merely grazes an edge). Both must contribute their area, or
    units stop tiling the floor.
    """
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if geom.area > 0 else []
    if hasattr(geom, "geoms"):
        return [p for part in geom.geoms for p in _polygon_parts(part)]
    return []


def _grid_shape(width: float, height: float, n_units: int) -> tuple[int, int]:
    """Pick (rows, cols) giving close to ``n_units`` cells, as square as possible."""
    best_score = None
    best_shape = (1, 1)
    for rows in range(1, MAX_UNITS_PER_FLOOR + 1):
        for cols in range(1, MAX_UNITS_PER_FLOOR + 1):
            if rows * cols > MAX_UNITS_PER_FLOOR:
                continue
            cell_w = width / cols
            cell_h = height / rows
            if cell_w <= 0 or cell_h <= 0:
                continue
            score = (abs(rows * cols - n_units), abs(math.log(cell_w / cell_h)))
            if best_score is None or score < best_score:
                best_score = score
                best_shape = (rows, cols)
    return best_shape


def _absorb_slivers(cells: list[Polygon]) -> list[Polygon]:
    """Merge undersized cells into the neighbour they share the most edge with.

    Preserves total area, so the units still tile the floor exactly.
    """
    kept = [c for c in cells if c.area >= MIN_UNIT_AREA_SQM]
    slivers = [c for c in cells if c.area < MIN_UNIT_AREA_SQM]

    if not kept:
        # Whole floor is smaller than one nominal unit -- it becomes one unit.
        merged = unary_union(cells)
        return [merged] if isinstance(merged, Polygon) else list(merged.geoms)

    for sliver in sorted(slivers, key=lambda c: c.area):
        best_index = max(
            range(len(kept)),
            key=lambda i: (
                kept[i].boundary.intersection(sliver.boundary).length,
                -kept[i].distance(sliver),
            ),
        )
        merged = unary_union([kept[best_index], sliver]).buffer(0)
        if isinstance(merged, Polygon):
            kept[best_index] = merged
        else:
            # Not actually adjacent -- leave the sliver as its own unit rather
            # than producing a MultiPolygon "unit".
            kept.append(sliver)
    return kept


def subdivide_footprint(footprint_m: Polygon) -> list[Polygon]:
    """Cut a metre-space footprint into unit polygons that tile it exactly."""
    if footprint_m.is_empty or footprint_m.area <= 0:
        raise SegmentationError("footprint has no area")

    n_units = max(1, min(MAX_UNITS_PER_FLOOR, round(footprint_m.area / TARGET_UNIT_AREA_SQM)))
    min_x, min_y, max_x, max_y = footprint_m.bounds
    rows, cols = _grid_shape(max_x - min_x, max_y - min_y, n_units)

    cell_w = (max_x - min_x) / cols
    cell_h = (max_y - min_y) / rows

    cells: list[Polygon] = []
    # Row 0 is the southern strip, so units read bottom-left to top-right.
    for row in range(rows):
        for col in range(cols):
            cell = box(
                min_x + col * cell_w,
                min_y + row * cell_h,
                min_x + (col + 1) * cell_w,
                min_y + (row + 1) * cell_h,
            )
            cells.extend(_polygon_parts(footprint_m.intersection(cell)))

    if not cells:
        raise SegmentationError("subdivision produced no units")
    return _absorb_slivers(cells)


def _unit_type(building_type: str | None, floor_number: int, index: int) -> str:
    """Synthesise a plausible mixed-use stack for the demo."""
    if building_type in ("commercial", "retail", "office"):
        return "commercial"
    if floor_number == 0:
        return "parking" if index == 0 else "commercial"
    return "residential"


def segment_building(
    footprint: dict,
    ulpin_2d: str,
    height: float | None = None,
    levels: int | None = None,
    building_type: str | None = None,
) -> dict:
    """Produce the full floor/unit breakdown for one building.

    ``footprint`` is a GeoJSON Polygon in lon/lat. Returns floors (with the
    base altitude and height the 3D viewer extrudes from) and, per floor, the
    unit polygons with their 3D ULPINs.
    """
    # Imported here to keep this module usable standalone in geometry tests.
    from services.ulpin_generator import floor_prefix, generate_ulpin_3d, unit_number_for

    geom = shape(footprint)
    if not isinstance(geom, Polygon):
        raise SegmentationError(f"expected a GeoJSON Polygon, got {geom.geom_type}")

    centroid = geom.centroid
    to_metres, to_lonlat = _projection(centroid.y, centroid.x)
    footprint_m = _map_polygon(geom, to_metres)

    level_count = infer_levels(height, levels)
    total_height = infer_height(height, level_count)
    floor_height = total_height / level_count

    # The same interior layout is reused on every storey, which matches how
    # real apartment blocks stack and keeps unit numbering predictable.
    unit_shapes_m = subdivide_footprint(footprint_m)

    floors = []
    for floor_number in range(level_count):
        units = []
        for index, unit_m in enumerate(unit_shapes_m):
            unit_type = _unit_type(building_type, floor_number, index)
            unit_number = unit_number_for(floor_number, index)
            units.append(
                {
                    "ulpin_3d": generate_ulpin_3d(ulpin_2d, floor_number, unit_number, unit_type),
                    "unit_number": unit_number,
                    "unit_type": unit_type,
                    "area_sqft": round(unit_m.area * SQM_TO_SQFT, 1),
                    "polygon": mapping(_map_polygon(unit_m, to_lonlat)),
                }
            )
        floors.append(
            {
                "floor_number": floor_number,
                "ulpin_3d_prefix": floor_prefix(ulpin_2d, floor_number),
                "base_z": round(floor_number * floor_height, 2),
                "height": round(floor_height, 2),
                "unit_count": len(units),
                "units": units,
            }
        )

    return {
        "ulpin_2d": ulpin_2d,
        "levels": level_count,
        "total_height": round(total_height, 2),
        "floor_height": round(floor_height, 2),
        "footprint_area_sqft": round(footprint_m.area * SQM_TO_SQFT, 1),
        "floors": floors,
    }
