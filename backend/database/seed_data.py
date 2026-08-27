"""Generate the synthetic ownership register for the cached demo buildings.

    python -m database.seed_data

Runs the two core services over every building in data/demo_city and writes one
parcel row per unit, plus a short transaction history. Deterministic: the RNG is
seeded from each unit's ULPIN, so re-seeding reproduces identical data and the
committed database matches what a teammate regenerates.

All owner names, Aadhaar references and transactions below are FABRICATED.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

from database.db import SessionLocal, engine, init_db
from database.models import Base, Parcel, Transaction
from services import osm_service
from services.floor_segmenter import segment_building
from services.ulpin_generator import generate_ulpin_2d

FIRST_NAMES = [
    "Aarav", "Ananya", "Rohan", "Priya", "Vikram", "Meera", "Arjun", "Kavya",
    "Siddharth", "Divya", "Karthik", "Lakshmi", "Nikhil", "Sneha", "Rahul",
    "Aishwarya", "Manoj", "Deepa", "Suresh", "Anjali", "Pradeep", "Shreya",
]
LAST_NAMES = [
    "Sharma", "Reddy", "Iyer", "Nair", "Gowda", "Rao", "Kulkarni", "Menon",
    "Desai", "Shetty", "Patel", "Krishnan", "Bhat", "Hegde", "Prasad",
]
ORG_NAMES = [
    "Sunrise Retail Pvt Ltd", "Nandi Ventures LLP", "Cauvery Traders",
    "Bengaluru Facility Services", "Vidhana Enterprises", "Orion Softworks",
]
ENCUMBRANCE_NOTES = [
    "Home loan mortgage registered with a scheduled bank",
    "Lease deed registered for a 9-year term",
    "Civil suit pending before the jurisdictional court",
]

TODAY = date(2026, 8, 28)


def _owner_for(rng: random.Random, unit_type: str) -> str:
    if unit_type == "parking":
        return "Association of Apartment Owners (common)"
    if unit_type == "commercial":
        return rng.choice(ORG_NAMES)
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _transactions_for(rng: random.Random, unit: dict, owner: str, purchase_date: date) -> list[Transaction]:
    """A plausible chain ending in the current owner's acquisition."""
    rate_per_sqft = rng.randint(6000, 14000)
    price = round(unit["area_sqft"] * rate_per_sqft, -3)

    previous_owner = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    records = [
        Transaction(
            transaction_type="sale",
            transaction_date=purchase_date,
            amount_inr=price,
            from_party=previous_owner,
            to_party=owner,
        )
    ]

    if rng.random() < 0.35:
        records.append(
            Transaction(
                transaction_type="mortgage",
                transaction_date=purchase_date + timedelta(days=rng.randint(30, 900)),
                amount_inr=round(price * rng.uniform(0.4, 0.75), -3),
                from_party=owner,
                to_party=rng.choice(["State Bank of India", "HDFC Bank", "Canara Bank"]),
            )
        )
    if rng.random() < 0.2:
        records.append(
            Transaction(
                transaction_type="inheritance",
                transaction_date=purchase_date - timedelta(days=rng.randint(400, 3000)),
                amount_inr=None,
                from_party=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                to_party=previous_owner,
            )
        )
    return records


def build_parcels() -> list[Parcel]:
    parcels: list[Parcel] = []

    for building in osm_service.list_buildings():
        lat, lon = building["centroid"]
        ulpin_2d = generate_ulpin_2d(lat, lon)

        segmentation = segment_building(
            footprint=building["footprint"],
            ulpin_2d=ulpin_2d,
            height=building["height"],
            levels=building["levels"],
            building_type=building["building_type"],
        )

        for floor in segmentation["floors"]:
            for unit in floor["units"]:
                # Seeding from the ULPIN keeps a unit's owner stable across reseeds.
                rng = random.Random(unit["ulpin_3d"])
                owner = _owner_for(rng, unit["unit_type"])
                purchase_date = TODAY - timedelta(days=rng.randint(200, 6000))
                encumbered = rng.random() < 0.22

                parcels.append(
                    Parcel(
                        ulpin_3d=unit["ulpin_3d"],
                        parent_ulpin_2d=ulpin_2d,
                        osm_id=building["osm_id"],
                        floor_prefix=floor["ulpin_3d_prefix"],
                        floor_number=floor["floor_number"],
                        unit_number=unit["unit_number"],
                        unit_type=unit["unit_type"],
                        area_sqft=unit["area_sqft"],
                        base_z=floor["base_z"],
                        floor_height=floor["height"],
                        owner_name=owner,
                        owner_aadhaar_ref=f"XXXX-XXXX-{rng.randint(1000, 9999)}",
                        purchase_date=purchase_date,
                        encumbrance_flag=encumbered,
                        encumbrance_note=rng.choice(ENCUMBRANCE_NOTES) if encumbered else None,
                        geometry=json.dumps(unit["polygon"]),
                        transactions=_transactions_for(rng, unit, owner, purchase_date),
                    )
                )

    return parcels


def seed(reset: bool = True) -> tuple[int, int]:
    """Rebuild the register. Returns (parcel count, building count)."""
    if reset:
        Base.metadata.drop_all(engine)
    init_db()

    parcels = build_parcels()
    building_count = len({p.osm_id for p in parcels})

    with SessionLocal() as session:
        session.add_all(parcels)
        session.commit()
    return len(parcels), building_count


if __name__ == "__main__":
    parcel_count, building_count = seed()
    print(f"Seeded {parcel_count} parcels across {building_count} buildings.")
