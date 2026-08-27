"""Building selection and floor listing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import schemas
from database.db import get_session
from database.models import Parcel
from services import osm_service
from services.floor_segmenter import infer_height, infer_levels
from services.ulpin_generator import generate_ulpin_2d

router = APIRouter(prefix="/api/building", tags=["buildings"])


class SelectRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


def floor_label(floor_number: int) -> str:
    return "Ground" if floor_number == 0 else f"Floor {floor_number}"


def _selection(building: dict, session: Session) -> schemas.BuildingSelection:
    lat, lon = building["centroid"]
    ulpin_2d = generate_ulpin_2d(lat, lon)

    levels = infer_levels(building["height"], building["levels"])
    total_height = infer_height(building["height"], levels)

    # Prefer the seeded register over recomputing geometry: it is the source of
    # truth for what actually exists in the demo, and it is already indexed.
    area_sqft = session.scalar(
        select(func.sum(Parcel.area_sqft)).where(
            Parcel.parent_ulpin_2d == ulpin_2d, Parcel.floor_number == 0
        )
    )

    return schemas.BuildingSelection(
        **{k: building[k] for k in ("osm_id", "name", "address", "building_type", "centroid", "footprint")},
        levels=levels,
        height=building["height"],
        ulpin_2d=ulpin_2d,
        total_height=round(total_height, 2),
        floor_height=round(total_height / levels, 2),
        floor_count=levels,
        footprint_area_sqft=round(area_sqft or 0.0, 1),
    )


@router.get("", response_model=list[schemas.BuildingSummary])
def list_buildings():
    """All cached demo buildings, for the 2D map overlay."""
    return osm_service.list_buildings()


@router.post("/select", response_model=schemas.BuildingSelection)
def select_building(request: SelectRequest, session: Session = Depends(get_session)):
    """Resolve a map click to a building and its simulated base ULPIN."""
    try:
        building = osm_service.find_building_at(request.lat, request.lon)
    except osm_service.BuildingNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _selection(building, session)


@router.get("/{osm_id:path}/floors", response_model=schemas.FloorList)
def list_floors(osm_id: str, session: Session = Depends(get_session)):
    """Every floor of a building, with the altitudes the 3D view extrudes from."""
    try:
        building = osm_service.get_building(osm_id)
    except osm_service.BuildingNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lat, lon = building["centroid"]
    ulpin_2d = generate_ulpin_2d(lat, lon)

    rows = session.execute(
        select(
            Parcel.floor_number,
            Parcel.floor_prefix,
            Parcel.base_z,
            Parcel.floor_height,
            func.count(Parcel.ulpin_3d),
        )
        .where(Parcel.osm_id == osm_id)
        .group_by(Parcel.floor_number, Parcel.floor_prefix, Parcel.base_z, Parcel.floor_height)
        .order_by(Parcel.floor_number)
    ).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"no seeded floors for {osm_id!r}")

    return schemas.FloorList(
        osm_id=osm_id,
        ulpin_2d=ulpin_2d,
        floors=[
            schemas.FloorSummary(
                floor_number=floor_number,
                ulpin_3d_prefix=prefix,
                base_z=base_z,
                height=height,
                unit_count=count,
                label=floor_label(floor_number),
            )
            for floor_number, prefix, base_z, height, count in rows
        ],
    )
