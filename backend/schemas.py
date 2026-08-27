"""Pydantic response models -- the contract the frontend builds against."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from services.ulpin_generator import DISCLAIMER


class SimulatedMixin(BaseModel):
    """Every ULPIN-bearing response carries its own provenance warning, so the
    disclaimer cannot be lost between the API and the UI."""

    is_simulated: bool = True
    disclaimer: str = DISCLAIMER


class BuildingSummary(BaseModel):
    osm_id: str
    name: str | None = None
    address: str | None = None
    building_type: str | None = None
    levels: int | None = None
    height: float | None = None
    centroid: list[float] = Field(description="[lat, lon]")
    footprint: dict = Field(description="GeoJSON Polygon")


class BuildingSelection(SimulatedMixin, BuildingSummary):
    ulpin_2d: str
    total_height: float
    floor_height: float
    floor_count: int
    footprint_area_sqft: float


class FloorSummary(BaseModel):
    floor_number: int
    ulpin_3d_prefix: str
    unit_count: int
    base_z: float = Field(description="Metres above ground to the floor slab")
    height: float
    label: str = Field(description="Human label, e.g. 'Ground' or 'Floor 4'")


class FloorList(SimulatedMixin):
    osm_id: str
    ulpin_2d: str
    floors: list[FloorSummary]


class UnitSummary(BaseModel):
    ulpin_3d: str
    unit_number: int
    unit_type: str
    area_sqft: float
    base_z: float
    height: float
    encumbrance_flag: bool
    polygon: dict = Field(description="GeoJSON Polygon")


class UnitList(SimulatedMixin):
    ulpin_3d_prefix: str
    floor_number: int
    units: list[UnitSummary]


class TransactionRecord(BaseModel):
    transaction_id: int
    transaction_type: str
    transaction_date: date
    amount_inr: float | None = None
    from_party: str | None = None
    to_party: str


class UnitDetail(SimulatedMixin):
    ulpin_3d: str
    parent_ulpin_2d: str
    osm_id: str
    floor_number: int
    unit_number: int
    unit_type: str
    area_sqft: float
    owner_name: str
    owner_aadhaar_ref: str
    purchase_date: date
    encumbrance_flag: bool
    encumbrance_note: str | None = None
    polygon: dict
    transactions: list[TransactionRecord]


class ValidationResult(BaseModel):
    valid: bool
    is_simulated: bool = True
    disclaimer: str = DISCLAIMER
    registered: bool = Field(
        default=False,
        description="Whether this ULPIN exists in the demo register, as opposed "
                    "to merely being well-formed.",
    )
    parsed: dict | None = None
    error: str | None = None
