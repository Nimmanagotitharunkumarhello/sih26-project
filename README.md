# 3D ULPIN — Vertical Property Registry

A prototype that extends India's 2D land-parcel identifier (ULPIN / Bhu-Aadhaar)
into the vertical dimension, so that an individual **floor and unit** inside a
multi-storey building can carry its own unique, deterministic identifier.

Click a building on the 2D map → the backend resolves it to a base ULPIN, slices
it into floor volumes and units, and issues a 3D ULPIN for every unit, each with
its own ownership record and transaction history.

```
KA0501A3F9K2P70402
└─ base ULPIN ─┘││└── room 02 (1-based, within the floor)
   (14 chars)    │└─── floor 04
                 └──── (unit type is a separate DB/API field, not ID-encoded)
```

> **Simulated data.** Real ULPINs are issued by state revenue departments from
> surveyed cadastral records under DILRMP. Nothing here touches those records —
> identifiers are derived from OpenStreetMap building geometry for demonstration,
> and every API response and screen carries this disclaimer. Owner names,
> Aadhaar references and transactions are fabricated.

## Why it works offline

Judging venues have unreliable Wi-Fi, so nothing on the request path calls an
external API. `scripts/prefetch_osm.py` is the only code that talks to Overpass;
it is run once during development and commits `data/demo_city/buildings.geojson`.
The server, the database seed, and the 3D viewer all read from that file. No
Cesium ion token is used anywhere — the 3D scene is built from our own geometry.

The one thing that does need the network is the 2D basemap's street tiles. The
cached building footprints are drawn over a solid background, so with the network
down the map still shows every clickable building, just without streets beneath.

## Running it

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m database.seed_data                # builds the register, offline
.venv/Scripts/python -m uvicorn main:app --port 8000
```

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173, proxies /api to port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

To curate a different demo area (needs network, run once):

```bash
cd backend
.venv/Scripts/python scripts/prefetch_osm.py --bbox 12.96 77.58 13.00 77.64 --limit 50
.venv/Scripts/python -m database.seed_data
```

## Design

The interface is built as a **cadastral survey sheet**, not a dashboard: ink
linework on diazo print stock, square corners, a title block, a north arrow that
turns to match the camera. The vernacular is drafting, because the thing this
project does — slicing a building into its levels — is an *exploded axonometric*,
a drawing convention that already exists for exactly this purpose.

- **Palette** — one warm neutral family and exactly one accent: `paper #F1EEE7`
  through `#E3DDCE` for the drafting field, warm charcoal `#241F19` for ink, and
  lac red `#9C3D2E` for the parcel identifier and the selected level. Unit uses
  are told apart by **hatch** — solid, diagonal, cross, dot — the way a drawing
  distinguishes materials, so hue never has to carry them.
- **Type** — Satoshi for display and body, JetBrains Mono for every identifier,
  area and coordinate.
- **Signature** — the base ULPIN annotated with drafting dimension brackets
  (`├──┤`) labelled State / District / Tehsil / Village / Plot, the way a
  measurement is annotated along a plot edge. The vertical extension repeats the
  device as a descending stack in the unit record.
- **The 3D view is a true axonometric** — Cesium runs an orthographic frustum, so
  parallel edges stay parallel and the result reads as a drawing rather than a
  render. Levels deal out bottom-to-top when exploded, and the selected level
  gets a leader line and callout.

Quality floor: responsive to 430px, visible keyboard focus, and
`prefers-reduced-motion` honoured (the explode sequence snaps instead of easing).

## Architecture

```
Frontend (React + Vite)
  MapViewer.jsx      2D map, MapLibre GL + OpenFreeMap, click to select
  CesiumViewer.jsx   3D exploded floor stack, CesiumJS, no ion token
  BuildingPanel / FloorSelector / UnitGrid / OwnershipCard
         │ REST (JSON + GeoJSON)
Backend (FastAPI)
  services/ulpin_generator.py   ★ deterministic ULPIN generation + parsing
  services/floor_segmenter.py   ★ floor volumes and unit subdivision
  services/osm_service.py         reads the cached GeoJSON (never Overpass)
  routers/{buildings,floors,units}.py
  database/  SQLAlchemy models + deterministic synthetic seed → SQLite
         │
  data/demo_city/buildings.geojson   pre-fetched, committed, 50 buildings
```

The two starred modules are the substance; everything else is plumbing.

### ULPIN generation

The 14-character base is `[state:2 alpha][district:2][area:2][building:8]`.
Administrative codes come from a static bundled table (`data/admin_regions.json`)
rather than a live geocoder. The building code is a blake2b hash of the centroid
rounded to 6 decimals, base-encoded over an 8-character, 34-symbol alphabet
(digits plus A-Z minus the easily-misread I/O) — blake2b rather than Python's
`hash()`, which is salted per process and would renumber every parcel on
restart. That's a ~1.8×10¹² value space, wide enough that two distinct
buildings colliding is effectively impossible.

Floor and room are each **2 digits** (00-99). Room is a simple 1-based index
within its floor, not a conventional flat number — floor is already its own
segment, so there's no need to double-encode it. Unit type (residential,
commercial, parking, common) is a plain DB/API field, not part of the ID.

### Floor and unit segmentation

OSM supplies an outline and usually a level count, never interior layouts, so
unit boundaries are synthesised: the footprint is projected to local metres, cut
into a grid sized from a ~80 m² target unit, and each cell clipped back to the
outline. Undersized slivers are merged into the neighbour they share the most
edge with, so **units tile their floor exactly** — no gaps, no overlaps. Missing
tags fall back to `levels = height / 3.5`, then to 4 floors.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Status + cached-dataset metadata |
| `GET /api/building` | All cached footprints, for the map overlay |
| `POST /api/building/select` | `{lat, lon}` → building + base ULPIN (404 on open ground) |
| `GET /api/building/{osm_id}/floors` | Floors with extrusion altitudes |
| `GET /api/floor/{prefix}/units` | Units on one floor |
| `GET /api/unit/{ulpin_3d}` | Full ownership record + transactions |
| `GET /api/validate/{ulpin}` | Structure check, and whether it is registered |

`valid` (well-formed) and `registered` (exists in the register) are reported
separately so the UI can tell "malformed" from "unknown".

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
```

Covers ULPIN determinism and round-tripping, exact floor tiling (including
concave and undersized footprints), and every API contract end-to-end.

## Attribution

Building data © OpenStreetMap contributors, ODbL. Basemap tiles by OpenFreeMap
(© OpenMapTiles). 3D rendering by CesiumJS (Apache 2.0).
