import { UNIT_TYPE_LABELS, floorLabel, unitHatch } from '../theme';

/** A unit schedule — the table a drawing carries listing every unit on the
 *  level, rather than a grid of tiles. Rows are the natural form: each unit
 *  has a number, a use, an area and a status, all of which want a column. */
export default function UnitGrid({ floorNumber, units, selectedUlpin, onSelect }) {
  const typesPresent = [...new Set(units.map((unit) => unit.unit_type))];

  return (
    <section className="record-block">
      <h3 className="record-heading">
        {floorLabel(floorNumber)} schedule
        <span className="record-heading-count">{units.length} units</span>
      </h3>

      <div className="unit-schedule">
        {units.map((unit) => (
          <button
            key={unit.ulpin_3d}
            type="button"
            className={`unit-row${unit.ulpin_3d === selectedUlpin ? ' is-selected' : ''}`}
            onClick={() => onSelect(unit.ulpin_3d)}
          >
            <span className={`hatch ${unitHatch(unit.unit_type)}`} />
            <span>
              <span className="unit-id">{unit.unit_number}</span>
              <span className="unit-use">
                {UNIT_TYPE_LABELS[unit.unit_type] ?? unit.unit_type}
              </span>
            </span>
            {unit.encumbrance_flag && <span className="unit-encumbered">Enc</span>}
            <span className="unit-area">{Math.round(unit.area_sqft).toLocaleString('en-IN')} ft²</span>
          </button>
        ))}
      </div>

      <div className="legend">
        {typesPresent.map((type) => (
          <span key={type}>
            <i className={`hatch ${unitHatch(type)}`} />
            {UNIT_TYPE_LABELS[type] ?? type}
          </span>
        ))}
      </div>
    </section>
  );
}
