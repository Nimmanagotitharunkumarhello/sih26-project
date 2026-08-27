"""Deterministic generation and parsing of SIMULATED ULPINs.

A real ULPIN (Bhu-Aadhaar) is issued by state revenue departments from surveyed
cadastral records under DILRMP. Nothing in this module talks to those records --
it derives a ULPIN-*shaped* identifier from a building's coordinates so the
prototype has stable, meaningful IDs to demonstrate vertical (floor/unit) land
parcelling. Every identifier this module produces is tagged as simulated, and
callers are expected to surface that to the user.

The 2D base is 14 digits, matching the existing ULPIN width:

    [state:2][district:2][tehsil:3][village:3][plot:4]

The vertical extension -- the part this project contributes -- appends floor,
unit and unit-type segments:

    <14-digit base>-F<floor:2>-U<unit:4>-T<type:1>

The unit segment is 4 digits so it can carry the conventional flat number,
which encodes the floor (flat 1201 is on floor 12). Three digits would overflow
above the ninth floor -- and the demo dataset contains 29-storey towers.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

DISCLAIMER = (
    "Simulated identifier generated for prototype demonstration only. "
    "Not an official ULPIN / Bhu-Aadhaar issued under DILRMP."
)

#: Trailing segment of a 3D ULPIN. Kept small and stable -- these codes are
#: embedded in generated IDs, so renumbering them invalidates every stored ID.
UNIT_TYPE_CODES = {
    "residential": 1,
    "commercial": 2,
    "parking": 3,
    "common": 4,
}
UNIT_TYPE_BY_CODE = {code: name for name, code in UNIT_TYPE_CODES.items()}

#: Coordinates are rounded to this many decimals before hashing so that
#: floating-point noise in a footprint centroid cannot change the plot code.
#: 6 decimals is ~11cm at the equator -- well below building resolution.
COORD_PRECISION = 6

_ADMIN_REGIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "admin_regions.json"

_ULPIN_2D_RE = re.compile(r"^\d{14}$")
_ULPIN_3D_RE = re.compile(r"^(?P<base>\d{14})-F(?P<floor>\d{2})-U(?P<unit>\d{4})-T(?P<type>\d)$")


class UlpinError(ValueError):
    """Raised when a ULPIN cannot be generated or parsed."""


@lru_cache(maxsize=1)
def _load_admin_regions() -> dict:
    with _ADMIN_REGIONS_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def resolve_region(lat: float, lon: float) -> dict:
    """Map a coordinate to administrative codes using the bundled static table.

    Deliberately offline: no reverse-geocoding service is called, so the demo
    behaves identically with the network unplugged.
    """
    table = _load_admin_regions()
    for region in table["regions"]:
        min_lon, min_lat, max_lon, max_lat = region["bbox"]
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return region
    return table["default"]


def generate_plot_code(lat: float, lon: float) -> str:
    """Derive a stable 4-digit plot code from a coordinate.

    Uses blake2b rather than the builtin ``hash()`` because ``hash()`` is salted
    per process -- IDs must survive a server restart.
    """
    key = f"{round(lat, COORD_PRECISION):.{COORD_PRECISION}f},{round(lon, COORD_PRECISION):.{COORD_PRECISION}f}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return f"{int.from_bytes(digest, 'big') % 10000:04d}"


def generate_ulpin_2d(lat: float, lon: float) -> str:
    """Build the 14-digit simulated base ULPIN for a parcel centroid."""
    region = resolve_region(lat, lon)
    ulpin = (
        f"{region['state_code']}"
        f"{region['district_code']}"
        f"{region['tehsil_code']}"
        f"{region['village_code']}"
        f"{generate_plot_code(lat, lon)}"
    )
    if not _ULPIN_2D_RE.match(ulpin):
        raise UlpinError(f"admin_regions.json produced a malformed base ULPIN: {ulpin!r}")
    return ulpin


def generate_ulpin_3d(
    ulpin_2d: str,
    floor_number: int,
    unit_number: int,
    unit_type: str = "residential",
) -> str:
    """Append the vertical extension to a base ULPIN.

    ``floor_number`` is 0-indexed (0 = ground). ``unit_number`` is the
    human-facing unit number (e.g. 402), not an index.
    """
    if not _ULPIN_2D_RE.match(ulpin_2d):
        raise UlpinError(f"expected a 14-digit base ULPIN, got {ulpin_2d!r}")
    if not 0 <= floor_number <= 99:
        raise UlpinError(f"floor_number out of range (0-99): {floor_number}")
    if not 0 <= unit_number <= 9999:
        raise UlpinError(f"unit_number out of range (0-9999): {unit_number}")
    if unit_type not in UNIT_TYPE_CODES:
        raise UlpinError(f"unknown unit_type {unit_type!r}; expected one of {sorted(UNIT_TYPE_CODES)}")
    return f"{ulpin_2d}-F{floor_number:02d}-U{unit_number:04d}-T{UNIT_TYPE_CODES[unit_type]}"


def floor_prefix(ulpin_2d: str, floor_number: int) -> str:
    """The ``<base>-F<nn>`` prefix that identifies a whole floor."""
    if not _ULPIN_2D_RE.match(ulpin_2d):
        raise UlpinError(f"expected a 14-digit base ULPIN, got {ulpin_2d!r}")
    if not 0 <= floor_number <= 99:
        raise UlpinError(f"floor_number out of range (0-99): {floor_number}")
    return f"{ulpin_2d}-F{floor_number:02d}"


def unit_number_for(floor_number: int, index: int) -> int:
    """Conventional unit numbering: floor 4, index 1 -> 402.

    Ground floor units become 1..N (there is no "004"). ``index`` is 0-based.
    """
    if floor_number == 0:
        return index + 1
    return floor_number * 100 + index + 1


def parse_ulpin(ulpin: str) -> dict:
    """Decode a 2D or 3D ULPIN into its component fields."""
    ulpin = ulpin.strip()

    if _ULPIN_2D_RE.match(ulpin):
        return {
            "kind": "2d",
            "ulpin_2d": ulpin,
            "state_code": ulpin[0:2],
            "district_code": ulpin[2:4],
            "tehsil_code": ulpin[4:7],
            "village_code": ulpin[7:10],
            "plot_code": ulpin[10:14],
        }

    match = _ULPIN_3D_RE.match(ulpin)
    if not match:
        raise UlpinError(
            f"{ulpin!r} is not a valid ULPIN; expected 14 digits "
            "or <14 digits>-Fnn-Unnn-Tn"
        )

    type_code = int(match.group("type"))
    if type_code not in UNIT_TYPE_BY_CODE:
        raise UlpinError(f"unknown unit-type code {type_code} in {ulpin!r}")

    parsed = parse_ulpin(match.group("base"))
    parsed.update(
        kind="3d",
        ulpin_3d=ulpin,
        floor_number=int(match.group("floor")),
        unit_number=int(match.group("unit")),
        unit_type=UNIT_TYPE_BY_CODE[type_code],
    )
    return parsed


def validate_ulpin(ulpin: str) -> dict:
    """Non-raising wrapper around :func:`parse_ulpin` for the API layer."""
    try:
        return {
            "valid": True,
            "is_simulated": True,
            "disclaimer": DISCLAIMER,
            "parsed": parse_ulpin(ulpin),
        }
    except UlpinError as exc:
        return {
            "valid": False,
            "is_simulated": True,
            "disclaimer": DISCLAIMER,
            "error": str(exc),
        }
