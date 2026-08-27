import { floorLabel } from '../theme';

/** The level index. Ordered top level first (via column-reverse) so it reads
 *  in the same direction as the axonometric it sits beside, and each row
 *  carries a rail showing how high that level sits in the building. */
export default function FloorSelector({ floors, selectedFloor, onSelect }) {
  const topZ = floors[floors.length - 1]?.base_z || 1;

  return (
    <section className="record-block">
      <h3 className="record-heading">
        Level index
        <span className="record-heading-count">{floors.length} levels</span>
      </h3>

      <div className="level-index">
        {floors.map((floor) => (
          <button
            key={floor.ulpin_3d_prefix}
            type="button"
            className={`level-row${floor.floor_number === selectedFloor ? ' is-selected' : ''}`}
            onClick={() => onSelect(floor.floor_number)}
          >
            <span className="level-row-tag">
              {floor.floor_number === 0 ? 'GND' : `L${String(floor.floor_number).padStart(2, '0')}`}
            </span>
            <span className="level-row-rail">
              <i style={{ width: `${Math.max(4, (floor.base_z / topZ) * 100)}%` }} />
            </span>
            <span className="level-row-units">{floor.unit_count}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export { floorLabel };
