"""Deterministic generation and parsing of SIMULATED ULPINs.

A real ULPIN (Bhu-Aadhaar) is issued by state revenue departments from surveyed
cadastral records under DILRMP. Nothing in this module talks to those records --
it derives a ULPIN-*shaped* identifier from a building's coordinates so the
prototype has stable, meaningful IDs to demonstrate vertical (floor/room)
land parcelling. Every identifier this module produces is tagged as
simulated, and callers are expected to surface that to the user.

The format is 18 characters, no separators:

    [state:2 alpha][district:2][area:2][building:8][floor:2][room:2]

State is a 2-letter alpha code. District and area are 2-digit administrative
codes. Building is an 8-character code from a 34-symbol alphabet (digits plus
A-Z minus the easily-misread I/O), deterministically derived from the
building's centroid -- 34**8 (~1.8e12) values, wide enough that two distinct
buildings colliding is effectively impossible. Floor and room are 2-digit
sequences (00-99); room is a simple 1-based index within its floor, not a
conventional flat number, since floor is already its own segment.

The 14-character building base (state+district+area+building) is generated
on its own via ``generate_ulpin_2d`` and identifies a building; the full
18-character ID via ``generate_ulpin_3d`` identifies one room.
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

#: Coordinates are rounded to this many decimals before hashing so that
#: floating-point noise in a footprint centroid cannot change the plot code.
#: 6 decimals is ~11cm at the equator -- well below building resolution.
COORD_PRECISION = 6

#: Digits plus A-Z minus I/O, which are easily misread as 1/0 when a code is
#: copied by hand. 34 symbols.
BUILDING_CODE_ALPHABET = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"
BUILDING_CODE_LENGTH = 8

_ADMIN_REGIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "admin_regions.json"

_ULPIN_2D_RE = re.compile(r"^(?P<state>[A-Z]{2})(?P<district>\d{2})(?P<area>\d{2})(?P<building>[0-9A-HJ-NP-Z]{8})$")
_ULPIN_3D_RE = re.compile(_ULPIN_2D_RE.pattern[:-1] + r"(?P<floor>\d{2})(?P<room>\d{2})$")


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


def generate_building_code(lat: float, lon: float) -> str:
    """Derive a stable 8-character building code from a coordinate.

    Uses blake2b rather than the builtin ``hash()`` because ``hash()`` is salted
    per process -- IDs must survive a server restart.
    """
    key = f"{round(lat, COORD_PRECISION):.{COORD_PRECISION}f},{round(lon, COORD_PRECISION):.{COORD_PRECISION}f}"
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    space = len(BUILDING_CODE_ALPHABET) ** BUILDING_CODE_LENGTH
    value = int.from_bytes(digest, "big") % space

    chars = []
    for _ in range(BUILDING_CODE_LENGTH):
        value, remainder = divmod(value, len(BUILDING_CODE_ALPHABET))
        chars.append(BUILDING_CODE_ALPHABET[remainder])
    return "".join(reversed(chars))


def generate_ulpin_2d(lat: float, lon: float) -> str:
    """Build the 14-character simulated base ULPIN for a building centroid."""
    region = resolve_region(lat, lon)
    ulpin = (
        f"{region['alpha_state_code']}"
        f"{region['district_code']}"
        f"{region['area_code']}"
        f"{generate_building_code(lat, lon)}"
    )
    if not _ULPIN_2D_RE.match(ulpin):
        raise UlpinError(f"admin_regions.json produced a malformed base ULPIN: {ulpin!r}")
    return ulpin


def generate_ulpin_3d(ulpin_2d: str, floor_number: int, room_number: int) -> str:
    """Append the vertical extension to a base ULPIN.

    ``floor_number`` is 0-indexed (0 = ground). ``room_number`` is a 1-based
    index within the floor (room 1, room 2, ...), not a conventional flat
    number -- floor is already encoded separately.
    """
    if not _ULPIN_2D_RE.match(ulpin_2d):
        raise UlpinError(f"expected a 14-character base ULPIN, got {ulpin_2d!r}")
    if not 0 <= floor_number <= 99:
        raise UlpinError(f"floor_number out of range (0-99): {floor_number}")
    if not 0 <= room_number <= 99:
        raise UlpinError(f"room_number out of range (0-99): {room_number}")
    return f"{ulpin_2d}{floor_number:02d}{room_number:02d}"


def floor_prefix(ulpin_2d: str, floor_number: int) -> str:
    """The ``<base><nn>`` prefix that identifies a whole floor."""
    if not _ULPIN_2D_RE.match(ulpin_2d):
        raise UlpinError(f"expected a 14-character base ULPIN, got {ulpin_2d!r}")
    if not 0 <= floor_number <= 99:
        raise UlpinError(f"floor_number out of range (0-99): {floor_number}")
    return f"{ulpin_2d}{floor_number:02d}"


def room_number_for(index: int) -> int:
    """Conventional room numbering within a floor: index 0 -> room 1."""
    return index + 1


def parse_ulpin(ulpin: str) -> dict:
    """Decode a 14-character (building) or 18-character (room) ULPIN into its
    component fields."""
    ulpin = ulpin.strip()

    match_2d = _ULPIN_2D_RE.match(ulpin)
    if match_2d:
        return {
            "kind": "2d",
            "ulpin_2d": ulpin,
            "state_code": match_2d.group("state"),
            "district_code": match_2d.group("district"),
            "area_code": match_2d.group("area"),
            "building_code": match_2d.group("building"),
        }

    match_3d = _ULPIN_3D_RE.match(ulpin)
    if not match_3d:
        raise UlpinError(
            f"{ulpin!r} is not a valid ULPIN; expected 14 characters "
            "(building) or 18 characters (room)"
        )

    parsed = parse_ulpin(ulpin[:14])
    parsed.update(
        kind="3d",
        ulpin_3d=ulpin,
        floor_number=int(match_3d.group("floor")),
        room_number=int(match_3d.group("room")),
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
