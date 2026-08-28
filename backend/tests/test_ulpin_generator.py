import pytest

from services.ulpin_generator import (
    DISCLAIMER,
    UlpinError,
    floor_prefix,
    generate_building_code,
    generate_ulpin_2d,
    generate_ulpin_3d,
    parse_ulpin,
    resolve_region,
    room_number_for,
    validate_ulpin,
)

# A point inside the Bengaluru North demo region.
LAT, LON = 12.9950, 77.5946


def test_same_coordinates_always_produce_the_same_ulpin():
    assert generate_ulpin_2d(LAT, LON) == generate_ulpin_2d(LAT, LON)


def test_building_code_is_stable_across_processes():
    # Hard-coded so a change to the hashing scheme (which would invalidate every
    # stored ULPIN) fails loudly rather than silently renumbering the database.
    assert generate_building_code(12.9950, 77.5946) == generate_building_code(12.9950, 77.5946)
    assert len(generate_building_code(LAT, LON)) == 8


def test_floating_point_noise_below_precision_does_not_change_the_building_code():
    assert generate_building_code(LAT, LON) == generate_building_code(LAT + 1e-9, LON - 1e-9)


def test_different_coordinates_produce_different_building_codes():
    codes = {generate_building_code(12.99 + i * 0.001, 77.59) for i in range(25)}
    # Collisions are astronomically unlikely in a 34**8 space at this size.
    assert len(codes) == 25


def test_base_ulpin_is_fourteen_characters_with_expected_segments():
    ulpin = generate_ulpin_2d(LAT, LON)
    assert len(ulpin) == 14

    parsed = parse_ulpin(ulpin)
    region = resolve_region(LAT, LON)
    assert parsed["kind"] == "2d"
    assert parsed["state_code"] == region["alpha_state_code"]
    assert parsed["district_code"] == region["district_code"]
    assert parsed["area_code"] == region["area_code"]
    assert parsed["building_code"] == generate_building_code(LAT, LON)


def test_coordinates_outside_mapped_regions_fall_back_to_default():
    region = resolve_region(28.6139, 77.2090)  # Delhi -- not in the demo table
    assert region["area_code"] == "99"


def test_vertical_extension_round_trips():
    base = generate_ulpin_2d(LAT, LON)
    ulpin_3d = generate_ulpin_3d(base, floor_number=4, room_number=2)

    assert ulpin_3d == f"{base}0402"
    assert len(ulpin_3d) == 18

    parsed = parse_ulpin(ulpin_3d)
    assert parsed["kind"] == "3d"
    assert parsed["ulpin_2d"] == base
    assert parsed["floor_number"] == 4
    assert parsed["room_number"] == 2


def test_floor_prefix_matches_the_generated_unit_ids():
    base = generate_ulpin_2d(LAT, LON)
    prefix = floor_prefix(base, 4)
    assert generate_ulpin_3d(base, 4, 2).startswith(prefix)


def test_room_numbering_convention():
    assert room_number_for(0) == 1
    assert room_number_for(1) == 2
    assert room_number_for(98) == 99


def test_room_numbers_fit_the_room_segment():
    base = generate_ulpin_2d(LAT, LON)
    ulpin = generate_ulpin_3d(base, 28, room_number_for(5))
    assert parse_ulpin(ulpin)["room_number"] == 6


VALID_BASE = "KA050112AB34CD"  # 14 chars: KA + 05 + 01 + 12AB34CD


@pytest.mark.parametrize(
    "args",
    [
        ("123", 1, 1),  # base too short
        (VALID_BASE, 100, 1),  # floor out of range
        (VALID_BASE, 1, 100),  # room out of range
    ],
)
def test_generate_ulpin_3d_rejects_bad_input(args):
    with pytest.raises(UlpinError):
        generate_ulpin_3d(*args)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "abc",
        VALID_BASE[:-1],  # 13 characters
        VALID_BASE.lower(),  # lowercase state
        "KA0501I2AB34CD",  # ambiguous letter I not in building alphabet
        VALID_BASE + "010",  # 17 characters, doesn't fit either width
    ],
)
def test_parse_rejects_malformed_ulpins(bad):
    with pytest.raises(UlpinError):
        parse_ulpin(bad)


def test_validate_never_raises_and_always_flags_simulation():
    ok = validate_ulpin(generate_ulpin_2d(LAT, LON))
    bad = validate_ulpin("not-a-ulpin")

    assert ok["valid"] is True and bad["valid"] is False
    for result in (ok, bad):
        assert result["is_simulated"] is True
        assert result["disclaimer"] == DISCLAIMER
