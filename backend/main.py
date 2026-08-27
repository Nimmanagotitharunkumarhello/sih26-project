"""3D ULPIN prototype API.

Serves simulated vertical land-parcel identifiers over a pre-fetched OSM
dataset. Makes no outbound network calls at request time -- see
services/osm_service.py.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.db import init_db
from routers import buildings, floors, units
from services import osm_service
from services.ulpin_generator import DISCLAIMER

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="3D ULPIN & Vertical Property Mapping API",
    description=(
        "Prototype API generating floor- and unit-level property identifiers.\n\n"
        f"**{DISCLAIMER}**"
    ),
    version="0.1.0",
)

# The frontend is served from a different origin in dev (Vite) and in prod
# (Vercel), so the allowed origins are configurable.
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in ALLOWED_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(buildings.router)
app.include_router(floors.router)
app.include_router(units.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    """Confirms the cached dataset is present -- the demo's only hard dependency."""
    metadata = osm_service.dataset_metadata()
    return {
        "status": "ok",
        "offline_capable": True,
        "is_simulated": True,
        "disclaimer": DISCLAIMER,
        "dataset": metadata,
        "building_count": len(osm_service.list_buildings()),
    }
