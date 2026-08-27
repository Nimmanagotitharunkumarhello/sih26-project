/** Thin wrappers over the backend contracts. Paths are origin-relative so the
 *  dev proxy (vite.config.js) and a same-origin deploy both work unchanged. */

const BASE = import.meta.env.VITE_API_URL ?? '';

async function get(path) {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.detail || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

export async function fetchHealth() {
  return get('/api/health');
}

export async function fetchBuildings() {
  return get('/api/building');
}

export async function selectBuilding(lat, lon) {
  const response = await fetch(`${BASE}/api/building/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lat, lon }),
  });
  if (response.status === 404) return null; // clicked open ground
  if (!response.ok) throw new Error(`select failed: ${response.status}`);
  return response.json();
}

export async function fetchFloors(osmId) {
  return get(`/api/building/${osmId}/floors`);
}

export async function fetchUnits(floorPrefix) {
  return get(`/api/floor/${floorPrefix}/units`);
}

export async function fetchUnit(ulpin3d) {
  return get(`/api/unit/${ulpin3d}`);
}

export async function validateUlpin(ulpin) {
  return get(`/api/validate/${encodeURIComponent(ulpin)}`);
}

/** Buildings come back as records; the map wants a FeatureCollection. */
export function toFeatureCollection(buildings) {
  return {
    type: 'FeatureCollection',
    features: buildings.map((building) => ({
      type: 'Feature',
      id: building.osm_id,
      properties: {
        osm_id: building.osm_id,
        name: building.name,
        levels: building.levels,
        building_type: building.building_type,
      },
      geometry: building.footprint,
    })),
  };
}
