# ULPIN v2 format — design

Date: 2026-08-28

## Problem

The current simulated ULPIN uses a 4-digit hash for the plot/building code
(`generate_plot_code`), a 10,000-value space. Two distinct buildings in the
same village can collide, and floor/unit is bolted onto a *parcel* code
rather than a *building* having its own identity. This isn't enough to
uniquely identify a specific room in a specific building in a specific city.

## Format

18 characters, no separators:

```
KA 05 01 A3F9K2P7 04 02
SS DD AA BBBBBBBB FF RR
```

| Segment | Width | Charset | Meaning |
|---|---|---|---|
| State | 2 | A-Z | alpha state code (`KA`) |
| District/taluk | 2 | 0-9 | reuses today's `district_code` |
| Area | 2 | 0-9 | replaces today's `tehsil_code`+`village_code` |
| Building | 8 | 0-9,A-Z minus I/O | deterministic hash of building centroid |
| Floor | 2 | 0-9 | 00-99, unchanged semantics |
| Room | 2 | 0-9 | 00-99, 1-based sequence *within the floor* |

The 14-character building base (`SS DD AA BBBBBBBB`) keeps the same width as
today's 14-digit base ULPIN — just alnum instead of all-digit.

## Key decisions (from user)

- **Building code**: coordinate hash (stateless, deterministic), not a
  registry/counter. Widened from 4 decimal digits to 8 chars from a
  34-symbol alphabet (34⁸ ≈ 1.8×10¹² combinations) — this is the actual
  fix for cross-building collisions.
- **Unit type**: dropped from the ID entirely. The ID's own characters
  already make each room unique; `unit_type` stays a plain DB/API field
  (it already is one, independent of the ID string).
- **Formatting**: fully contiguous, no dashes — matches how a real
  ULPIN/Bhu-Aadhaar is written as one unbroken code.

## Consequential simplification: room numbering

Today's `unit_number` is a 4-digit *conventional flat number* that bakes the
floor into it (flat `1201` = floor 12, unit 01). Since floor is now its own
2-digit ID segment, room becomes a plain 1-based sequence per floor (01, 02,
…) — no more double-encoding the floor.

## Region data changes (`admin_regions.json`)

- Add `alpha_state_code` per region (`"KA"` for all three current demo
  regions, all in Bengaluru Urban / Karnataka).
- Replace `tehsil_code` (3 digits) + `village_code` (3 digits) with a single
  `area_code` (2 digits): North taluk → `01`, South taluk → `02`, Anekal →
  `03`, default → `99`.

## Blast radius

Verified by grep that everything outside the generator treats ULPINs as
opaque strings keyed by field name (`ulpin_2d`, `ulpin_3d`,
`parent_ulpin_2d`, `floor_prefix`) — routers, seed data, and the floor
segmenter need **no changes**, since function names/signatures in
`ulpin_generator.py` stay the same.

Files that do change:

- `backend/services/ulpin_generator.py` — core rewrite: regex, generation,
  parsing, plus the widened building-code alphabet
- `backend/data/admin_regions.json` — schema change described above
- `frontend/src/theme.js` — `ULPIN_SEGMENTS` (State/District/Area/Building)
- `frontend/src/components/BuildingPanel.jsx` — caption text ("14 digit" →
  "14 character")
- `frontend/src/components/OwnershipCard.jsx` — drop the `T#` (unit-type)
  row from the extension-stack visual; relabel the unit-number row as room
  number
- `backend/tests/test_ulpin_generator.py`, `test_api.py`,
  `test_floor_segmenter.py` — updated expectations
- `README.md` — format diagram

No DB migration: column widths (`String(14)`, `String(20)`, `String(32)`)
already fit the new lengths, and this is fabricated demo data regenerated
by reseeding, not live data requiring migration.

## Testing

- Update and run `backend/tests/test_ulpin_generator.py` (determinism,
  round-trip parsing, collision-space sanity) and the dependent test files
  above.
- Re-run the seed script and spot-check the frontend panel renders the new
  segment labels correctly.
