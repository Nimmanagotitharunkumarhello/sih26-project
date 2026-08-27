"""Unit listing for a single floor."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from database.db import get_session
from database.models import Parcel

router = APIRouter(prefix="/api/floor", tags=["floors"])


@router.get("/{ulpin_prefix}/units", response_model=schemas.UnitList)
def list_units(ulpin_prefix: str, session: Session = Depends(get_session)):
    """Units on one floor, keyed by the `<base>-Fnn` prefix."""
    parcels = session.scalars(
        select(Parcel).where(Parcel.floor_prefix == ulpin_prefix).order_by(Parcel.unit_number)
    ).all()

    if not parcels:
        raise HTTPException(status_code=404, detail=f"no units for floor prefix {ulpin_prefix!r}")

    return schemas.UnitList(
        ulpin_3d_prefix=ulpin_prefix,
        floor_number=parcels[0].floor_number,
        units=[
            schemas.UnitSummary(
                ulpin_3d=parcel.ulpin_3d,
                unit_number=parcel.unit_number,
                unit_type=parcel.unit_type,
                area_sqft=parcel.area_sqft,
                base_z=parcel.base_z,
                height=parcel.floor_height,
                encumbrance_flag=parcel.encumbrance_flag,
                polygon=json.loads(parcel.geometry),
            )
            for parcel in parcels
        ],
    )
