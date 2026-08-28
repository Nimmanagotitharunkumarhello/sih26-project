import UlpinDimension from './UlpinDimension';

export default function BuildingPanel({ building }) {
  return (
    <section className="record-block">
      <h2 className="parcel-name">{building.name || 'Unnamed structure'}</h2>
      <p className="parcel-address">
        {building.address || `${building.centroid[0].toFixed(5)}, ${building.centroid[1].toFixed(5)}`}
      </p>

      <UlpinDimension ulpin={building.ulpin_2d} caption="Parcel identifier" />

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
