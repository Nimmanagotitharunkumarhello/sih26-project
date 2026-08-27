import { useState } from 'react';
import { splitUlpin } from '../theme';

/** The signature element: the base ULPIN annotated the way a measurement is
 *  annotated along a plot edge — digits, a dimension bracket under each
 *  segment, then the segment's name. Grid columns are weighted by digit count,
 *  which the monospace face makes align exactly with the digits above. */
function DimensionedUlpin({ ulpin2d }) {
  const [copied, setCopied] = useState(false);
  const segments = splitUlpin(ulpin2d);
  const columns = segments.map((segment) => `${segment.digits}fr`).join(' ');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(ulpin2d);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard is blocked over plain http in some browsers. The number is
      // selectable on screen either way, so this needs no error surface.
    }
  };

  return (
    <div className="ulpin-dim">
      <div className="ulpin-dim-caption">
        <span>Parcel identifier · 14 digit</span>
        <button type="button" className="ulpin-copy" onClick={copy}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div className="ulpin-grid" style={{ gridTemplateColumns: columns }}>
        {segments.map((segment) => (
          <span key={segment.key} className="ulpin-digits">
            {segment.value}
          </span>
        ))}
        {segments.map((segment) => (
          <span key={`${segment.key}-bracket`} className="ulpin-bracket" />
        ))}
        {segments.map((segment) => (
          <span key={`${segment.key}-label`} className="ulpin-seg-label">
            {segment.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function BuildingPanel({ building }) {
  return (
    <section className="record-block">
      <h2 className="parcel-name">{building.name || 'Unnamed structure'}</h2>
      <p className="parcel-address">
        {building.address || `${building.centroid[0].toFixed(5)}, ${building.centroid[1].toFixed(5)}`}
      </p>

      <DimensionedUlpin ulpin2d={building.ulpin_2d} />

      <dl className="measure-grid">
        <div>
          <dt>Levels</dt>
          <dd>{building.floor_count}</dd>
        </div>
        <div>
          <dt>Height</dt>
          <dd>
            {building.total_height} <span className="measure-unit">m</span>
          </dd>
        </div>
        <div>
          <dt>Floor plate</dt>
          <dd>
            {Math.round(building.footprint_area_sqft).toLocaleString('en-IN')}{' '}
            <span className="measure-unit">ft²</span>
          </dd>
        </div>
        <div>
          <dt>Recorded use</dt>
          <dd style={{ fontSize: '13px', textTransform: 'capitalize' }}>
            {building.building_type}
          </dd>
        </div>
      </dl>
    </section>
  );
}
