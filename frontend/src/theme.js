/** One warm neutral family, one accent.
 *
 *  The earlier palette carried four accent hues and mixed a warm ground with
 *  cool ink, which is what made it read as assembled rather than designed.
 *  Unit uses are now told apart by hatch — the way a drawing distinguishes
 *  materials — so hue stays reserved for the one thing that matters. */

export const INK = {
  paper0: '#FAF8F4', // raised
  paper1: '#F1EEE7', // ground
  paper2: '#E7E2D8', // recessed
  line: '#D6D0C3',
  ink3: '#8F8778', // faint
  ink2: '#5A5248', // secondary
  ink1: '#241F19', // primary, a warm charcoal rather than black
  accent: '#9C3D2E', // lac red — boundary and seal ink
  /** The drafting-table ground the axonometric is cleared to. Kept in step
   *  with the `--field` custom property in styles.css, which paints the same
   *  colour onto Cesium's widget element — its own stylesheet defaults that to
   *  black, which shows through if left alone. */
  field: '#E3DDCE',
};

/** Unit uses are drawn, not coloured. `hatch` names a CSS class; `weight`
 *  drives the fill strength of the same accent in the axonometric. */
export const UNIT_TYPES = {
  residential: { label: 'Residential', hatch: 'hatch-solid', weight: 0.72 },
  commercial: { label: 'Commercial', hatch: 'hatch-diagonal', weight: 0.5 },
  parking: { label: 'Parking', hatch: 'hatch-cross', weight: 0.32 },
  common: { label: 'Common area', hatch: 'hatch-dot', weight: 0.2 },
};

export const UNIT_TYPE_LABELS = Object.fromEntries(
  Object.entries(UNIT_TYPES).map(([key, value]) => [key, value.label]),
);


export function unitHatch(unitType) {
  return UNIT_TYPES[unitType]?.hatch ?? 'hatch-solid';
}

export function unitWeight(unitType) {
  return UNIT_TYPES[unitType]?.weight ?? 0.3;
}

export function formatInr(amount) {
  if (amount == null) return '—';
  if (amount >= 1e7) return `₹${(amount / 1e7).toFixed(2)} Cr`;
  if (amount >= 1e5) return `₹${(amount / 1e5).toFixed(2)} L`;
  return `₹${amount.toLocaleString('en-IN')}`;
}

export function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function floorLabel(floorNumber) {
  return floorNumber === 0 ? 'Ground' : `Level ${floorNumber}`;
}

/** The 14-character base ULPIN, split into the segments a dimension line annotates. */
export const ULPIN_SEGMENTS = [
  { key: 'state', label: 'State', digits: 2 },
  { key: 'district', label: 'District', digits: 2 },
  { key: 'area', label: 'Area', digits: 2 },
  { key: 'building', label: 'Building', digits: 8 },
];

export function splitUlpin(ulpin2d) {
  let offset = 0;
  return ULPIN_SEGMENTS.map((segment) => {
    const value = ulpin2d.slice(offset, offset + segment.digits);
    offset += segment.digits;
    return { ...segment, value };
  });
}
