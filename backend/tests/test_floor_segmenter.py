import pytest
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

from services.floor_segmenter import (
    DEFAULT_LEVELS,
    MAX_UNITS_PER_FLOOR,
    SegmentationError,
    infer_height,
    infer_levels,
    segment_building,
    subdivide_footprint,
)
from services.ulpin_generator import generate_ulpin_2d, parse_ulpin

LAT, LON = 12.9950, 77.5946
ULPIN_2D = generate_ulpin_2d(LAT, LON)


def rect_footprint(width_deg=0.0002, height_deg=0.00015):
    """A small rectangle near the demo region (~22m x 17m)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [LON, LAT],
            [LON + width_deg, LAT],
            [LON + width_deg, LAT + height_deg],
            [LON, LAT + height_deg],
            [LON, LAT],
        ]],
    }


# --- level / height inference -------------------------------------------------

def test_levels_tag_wins_when_present():
    assert infer_levels(height=30.0, levels=8) == 8


def test_levels_derived_from_height_when_tag_missing():
    assert infer_levels(height=21.0, levels=None) == 6  # 21 / 3.5


def test_levels_fall_back_to_default_when_both_missing():
    assert infer_levels(height=None, levels=None) == DEFAULT_LEVELS


def test_height_derived_from_levels_when_missing():
    assert infer_height(height=None, levels=4) == 14.0


# --- subdivision geometry -----------------------------------------------------

def _to_metres_polygon(footprint):
    """Reproduce the module's projection so we can assert in metre space."""
    from services.floor_segmenter import _map_polygon, _projection

    geom = shape(footprint)
    to_metres, _ = _projection(geom.centroid.y, geom.centroid.x)
    return _map_polygon(geom, to_metres)


def test_units_tile_a_rectangular_floor_without_gaps_or_overlaps():
    footprint_m = _to_metres_polygon(rect_footprint(0.0006, 0.0004))  # ~65m x 44m
    units = subdivide_footprint(footprint_m)

    assert len(units) > 1

    # No overlaps: pairwise intersections have negligible area.
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            assert units[i].intersection(units[j]).area < 1e-6

    # No gaps: the union recovers the whole floor.
    covered = unary_union(units)
    assert covered.area == pytest.approx(footprint_m.area, rel=1e-9)
    assert footprint_m.difference(covered).area < 1e-6


def test_units_tile_a_concave_footprint():
    # L-shaped building.
    l_shape = Polygon([(0, 0), (40, 0), (40, 20), (20, 20), (20, 40), (0, 40)])
    units = subdivide_footprint(l_shape)

    covered = unary_union(units)
    assert covered.area == pytest.approx(l_shape.area, rel=1e-9)
    assert all(u.area > 0 for u in units)


def test_unit_count_is_capped_for_legibility():
    huge = Polygon([(0, 0), (400, 0), (400, 400), (0, 400)])  # 160,000 sqm
    assert len(subdivide_footprint(huge)) <= MAX_UNITS_PER_FLOOR


def test_tiny_footprint_becomes_a_single_unit():
    tiny = Polygon([(0, 0), (3, 0), (3, 3), (0, 3)])  # 9 sqm, below the sliver floor
    assert len(subdivide_footprint(tiny)) == 1


def test_empty_footprint_is_rejected():
    with pytest.raises(SegmentationError):
        subdivide_footprint(Polygon())


# --- full building segmentation ----------------------------------------------

def test_segment_building_produces_one_entry_per_floor():
    result = segment_building(rect_footprint(), ULPIN_2D, height=21.0, levels=6)

    assert result["levels"] == 6
    assert len(result["floors"]) == 6
    assert result["floor_height"] == pytest.approx(3.5)


def test_floor_altitudes_stack_without_overlapping():
    result = segment_building(rect_footprint(), ULPIN_2D, height=21.0, levels=6)

    for floor in result["floors"]:
        expected_base = floor["floor_number"] * result["floor_height"]
        assert floor["base_z"] == pytest.approx(expected_base, abs=0.01)
        assert floor["height"] == pytest.approx(result["floor_height"])


def test_every_unit_carries_a_parseable_3d_ulpin_for_its_own_floor():
    result = segment_building(rect_footprint(0.0006, 0.0004), ULPIN_2D, height=21.0, levels=6)

    seen = set()
    for floor in result["floors"]:
        for unit in floor["units"]:
            parsed = parse_ulpin(unit["ulpin_3d"])
            assert parsed["ulpin_2d"] == ULPIN_2D
            assert parsed["floor_number"] == floor["floor_number"]
            assert parsed["unit_type"] == unit["unit_type"]
            assert unit["ulpin_3d"].startswith(floor["ulpin_3d_prefix"])
            seen.add(unit["ulpin_3d"])

    total_units = sum(f["unit_count"] for f in result["floors"])
    assert len(seen) == total_units  # every 3D ULPIN is unique


def test_ground_floor_is_mixed_use_and_upper_floors_are_residential():
    result = segment_building(rect_footprint(0.0006, 0.0004), ULPIN_2D, height=21.0, levels=6)

    ground_types = {u["unit_type"] for u in result["floors"][0]["units"]}
    upper_types = {u["unit_type"] for u in result["floors"][3]["units"]}

    assert "parking" in ground_types
    assert upper_types == {"residential"}


def test_commercial_buildings_are_commercial_throughout():
    result = segment_building(
        rect_footprint(0.0006, 0.0004), ULPIN_2D, height=21.0, levels=6, building_type="commercial"
    )
    types = {u["unit_type"] for f in result["floors"] for u in f["units"]}
    assert types == {"commercial"}


def test_unit_areas_sum_to_the_footprint_area():
    result = segment_building(rect_footprint(0.0006, 0.0004), ULPIN_2D, height=21.0, levels=6)

    floor_area = sum(u["area_sqft"] for u in result["floors"][0]["units"])
    assert floor_area == pytest.approx(result["footprint_area_sqft"], rel=1e-3)


def test_unit_polygons_are_returned_as_geojson_in_lon_lat():
    result = segment_building(rect_footprint(), ULPIN_2D, height=21.0, levels=6)
    polygon = result["floors"][0]["units"][0]["polygon"]

    assert polygon["type"] == "Polygon"
    lon, lat = polygon["coordinates"][0][0]
    assert LON - 0.01 < lon < LON + 0.01
    assert LAT - 0.01 < lat < LAT + 0.01


def test_non_polygon_geometry_is_rejected():
    with pytest.raises(SegmentationError):
        segment_building({"type": "Point", "coordinates": [LON, LAT]}, ULPIN_2D)
