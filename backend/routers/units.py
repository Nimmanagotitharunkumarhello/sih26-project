"""Full ownership record for one unit, plus ULPIN validation."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

import schemas
from database.db import get_session
from database.models import Parcel
from services.ulpin_generator import validate_ulpin

router = APIRouter(tags=["units"])


@router.get("/api/unit/{ulpin_3d}", response_model=schemas.UnitDetail)
def get_unit(ulpin_3d: str, session: Session = Depends(get_session)):
    parcel = session.get(Parcel, ulpin_3d)
    if parcel is None:
        raise HTTPException(status_code=404, detail=f"no unit registered as {ulpin_3d!r}")

    return schemas.UnitDetail(
        ulpin_3d=parcel.ulpin_3d,
        parent_ulpin_2d=parcel.parent_ulpin_2d,
        osm_id=parcel.osm_id,
        floor_number=parcel.floor_number,
        unit_number=parcel.unit_number,
        unit_type=parcel.unit_type,
        area_sqft=parcel.area_sqft,
        owner_name=parcel.owner_name,
        owner_aadhaar_ref=parcel.owner_aadhaar_ref,
        purchase_date=parcel.purchase_date,
        encumbrance_flag=parcel.encumbrance_flag,
        encumbrance_note=parcel.encumbrance_note,
        polygon=json.loads(parcel.geometry),
        transactions=[
            schemas.TransactionRecord(
                transaction_id=t.transaction_id,
                transaction_type=t.transaction_type,
                transaction_date=t.transaction_date,
                amount_inr=t.amount_inr,
                from_party=t.from_party,
                to_party=t.to_party,
            )
            for t in parcel.transactions
        ],
    )


@router.get("/api/validate/{ulpin}", response_model=schemas.ValidationResult)
def validate(ulpin: str, session: Session = Depends(get_session)):
    """Check a ULPIN's structure, and whether it exists in the demo register.

    A well-formed ULPIN is not necessarily a registered one -- the two are
    reported separately so the UI can distinguish "malformed" from "unknown".
    """
    result = validate_ulpin(ulpin)
    registered = result["valid"] and session.get(Parcel, ulpin.strip()) is not None
    return schemas.ValidationResult(**result, registered=registered)
