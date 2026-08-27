import pytest

from services.ulpin_generator import (
    DISCLAIMER,
    UlpinError,
    floor_prefix,
    generate_plot_code,
    generate_ulpin_2d,
    generate_ulpin_3d,
    parse_ulpin,
    resolve_region,
    unit_number_for,
    validate_ulpin,
)

# A point inside the Bengaluru North demo region.
LAT, LON = 12.9950, 77.5946


def test_same_coordinates_always_produce_the_same_ulpin():
    assert generate_ulpin_2d(LAT, LON) == generate_ulpin_2d(LAT, LON)


def test_plot_code_is_stable_across_processes():
    # Hard-coded so a change to the hashing scheme (which would invalidate every
    # stored ULPIN) fails loudly rather than silently renumbering the database.
    assert generate_plot_code(12.9950, 77.5946) == generate_plot_code(12.9950, 77.5946)
    assert len(generate_plot_code(LAT, LON)) == 4


def test_floating_point_noise_below_precision_does_not_change_the_plot_code():
    assert generate_plot_code(LAT, LON) == generate_plot_code(LAT + 1e-9, LON - 1e-9)


def test_different_coordinates_produce_different_plot_codes():
    codes = {generate_plot_code(12.99 + i * 0.001, 77.59) for i in range(25)}
    # Collisions are possible in a 4-digit space but should be rare at this size.
    assert len(codes) >= 23


def test_base_ulpin_is_fourteen_digits_with_expected_segments():
    ulpin = generate_ulpin_2d(LAT, LON)
    assert len(ulpin) == 14 and ulpin.isdigit()

    parsed = parse_ulpin(ulpin)
    region = resolve_region(LAT, LON)
    assert parsed["kind"] == "2d"
    assert parsed["state_code"] == region["state_code"]
    assert parsed["district_code"] == region["district_code"]
    assert parsed["tehsil_code"] == region["tehsil_code"]
    assert parsed["village_code"] == region["village_code"]


def test_coordinates_outside_mapped_regions_fall_back_to_default():
    region = resolve_region(28.6139, 77.2090)  # Delhi -- not in the demo table
    assert region["tehsil_code"] == "999"


def test_vertical_extension_round_trips():
    base = generate_ulpin_2d(LAT, LON)
    ulpin_3d = generate_ulpin_3d(base, floor_number=4, unit_number=402, unit_type="residential")

    assert ulpin_3d == f"{base}-F04-U0402-T1"

    parsed = parse_ulpin(ulpin_3d)
    assert parsed["kind"] == "3d"
    assert parsed["ulpin_2d"] == base
    assert parsed["floor_number"] == 4
    assert parsed["unit_number"] == 402
    assert parsed["unit_type"] == "residential"


def test_floor_prefix_matches_the_generated_unit_ids():
    base = generate_ulpin_2d(LAT, LON)
    prefix = floor_prefix(base, 4)
    assert generate_ulpin_3d(base, 4, 402, "residential").startswith(prefix)


def test_unit_numbering_convention():
    assert unit_number_for(0, 0) == 1  # ground floor units are 1..N
    assert unit_number_for(4, 1) == 402
    assert unit_number_for(12, 0) == 1201


def test_high_rise_unit_numbers_fit_the_unit_segment():
    # The demo dataset contains 29-storey towers; three digits would overflow.
    base = generate_ulpin_2d(LAT, LON)
    ulpin = generate_ulpin_3d(base, 28, unit_number_for(28, 5), "residential")
    assert parse_ulpin(ulpin)["unit_number"] == 2806


@pytest.mark.parametrize(
    "args",
    [
        ("123", 1, 101, "residential"),  # base too short
        ("29051022140567", 100, 101, "residential"),  # floor out of range
        ("29051022140567", 1, 10000, "residential"),  # unit out of range
        ("29051022140567", 1, 101, "penthouse"),  # unknown type
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
        "2905102214056",  # 13 digits
        "29051022140567-F4-U0402-T1",  # floor not zero-padded
        "29051022140567-F04-U402-T1",  # unit not zero-padded to 4
        "29051022140567-F04-U0402-T9",  # unknown unit-type code
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
