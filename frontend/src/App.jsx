import { useCallback, useEffect, useState } from 'react';
import MapViewer from './components/MapViewer';
import CesiumViewer from './components/CesiumViewer';
import BuildingPanel from './components/BuildingPanel';
import FloorSelector from './components/FloorSelector';
import UnitGrid from './components/UnitGrid';
import OwnershipCard from './components/OwnershipCard';
import {
  fetchBuildings,
  fetchFloors,
  fetchHealth,
  fetchUnit,
  fetchUnits,
  selectBuilding,
  toFeatureCollection,
} from './api';

/** Drafting furniture. The plan gets its scale bar from MapLibre, which knows
 *  the real scale; here the north arrow turns to match the camera, since the
 *  axonometric is viewed along a 45° heading and an arrow pointing up the
 *  screen would be stating something false. */
function DrawingFurniture({ mode }) {
  return (
    <div className="drawing-furniture">
      <div className="north-arrow">
        <svg
          width="15"
          height="24"
          viewBox="0 0 15 24"
          aria-hidden="true"
          style={{ transform: mode === 'plan' ? 'none' : 'rotate(-45deg)' }}
        >
          <path d="M7.5 1 L13 20 L7.5 15.5 L2 20 Z" fill="none" stroke="currentColor" strokeWidth="1" />
        </svg>
        N
      </div>
      {mode === 'axonometric' && (
        <p className="projection-note">Isometric · orthographic projection</p>
      )}
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [footprints, setFootprints] = useState(null);
  const [error, setError] = useState(null);

  const [building, setBuilding] = useState(null);
  const [floors, setFloors] = useState([]);
  const [selectedFloor, setSelectedFloor] = useState(null);
  const [units, setUnits] = useState([]);
  const [unitDetail, setUnitDetail] = useState(null);

  const [view, setView] = useState('plan');
  const [exploded, setExploded] = useState(true);
  const [busy, setBusy] = useState(false);
  const [missNote, setMissNote] = useState(false);

  useEffect(() => {
    Promise.all([fetchHealth(), fetchBuildings()])
      .then(([healthBody, buildings]) => {
        setHealth(healthBody);
        setFootprints(toFeatureCollection(buildings));
      })
      .catch((err) => setError(err.message));
  }, []);

  const openLevel = useCallback(async (floorList, floorNumber) => {
    const floor = floorList.find((f) => f.floor_number === floorNumber);
    if (!floor) return;
    setSelectedFloor(floorNumber);
    setUnitDetail(null);
    const body = await fetchUnits(floor.ulpin_3d_prefix);
    setUnits(body.units);
  }, []);

  const handleMapClick = useCallback(
    async (lat, lon) => {
      setBusy(true);
      setError(null);
      try {
        const selection = await selectBuilding(lat, lon);
        if (!selection) {
          // Open ground. Hold the current parcel, but say why nothing moved.
          setMissNote(true);
          setTimeout(() => setMissNote(false), 1800);
          return;
        }

        setMissNote(false);
        setBuilding(selection);
        setUnitDetail(null);

        const floorBody = await fetchFloors(selection.osm_id);
        setFloors(floorBody.floors);
        setView('axonometric');

        // Open a mid level — it shows the stack off better than the ground.
        const opening = floorBody.floors[Math.min(4, floorBody.floors.length - 1)];
        await openLevel(floorBody.floors, opening.floor_number);
      } catch (err) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
    },
    [openLevel],
  );

  const handleSelectFloor = useCallback(
    (floorNumber) => {
      openLevel(floors, floorNumber).catch((err) => setError(err.message));
    },
    [floors, openLevel],
  );

  const handleSelectUnit = useCallback((ulpin3d) => {
    fetchUnit(ulpin3d).then(setUnitDetail).catch((err) => setError(err.message));
  }, []);

  return (
    <div className="app">
      <header className="title-block">
        <div className="title-block-mark">
          <span className="registry-glyph">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path
                d="M1 12.5 L9 8 L17 12.5 M1 9 L9 4.5 L17 9 M1 5.5 L9 1 L17 5.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
              />
            </svg>
          </span>
          <div>
            <h1>Vertical Property Registry</h1>
            <p className="title-block-sub">Floor-level ULPIN · Bengaluru sheet</p>
          </div>
        </div>

        <div className="title-block-cells">
          <div className="tb-cell">
            <span className="tb-cell-label">Parcels</span>
            <span className="tb-cell-value">{health ? health.building_count : '—'}</span>
          </div>
          <div className="tb-cell">
            <span className="tb-cell-label">Source</span>
            <span className="tb-cell-value is-live">{health ? 'Cached' : '—'}</span>
          </div>
        </div>

        <div className="tb-controls">
          <div className="view-toggle" role="group" aria-label="Drawing view">
            <button
              type="button"
              className={view === 'plan' ? 'is-active' : ''}
              onClick={() => setView('plan')}
            >
              Plan
            </button>
            <button
              type="button"
              className={view === 'axonometric' ? 'is-active' : ''}
              onClick={() => setView('axonometric')}
              disabled={!building}
            >
              Axonometric
            </button>
          </div>

          {view === 'axonometric' && (
            <button
              type="button"
              className="assembly-toggle"
              onClick={() => setExploded((value) => !value)}
            >
              {exploded ? 'Assemble' : 'Explode'}
            </button>
          )}
        </div>
      </header>

      <main className="sheet">
        <div className="drawing">
          {/* Both surfaces stay mounted: rebuilding the Cesium scene on every
              toggle is slow, and the plan keeps its camera position. */}
          <div className={`drawing-layer${view === 'plan' ? ' is-visible' : ''}`}>
            <MapViewer
              buildings={footprints}
              selectedOsmId={building?.osm_id}
              onSelectPoint={handleMapClick}
            />
          </div>
          <div className={`drawing-layer${view === 'axonometric' ? ' is-visible' : ''}`}>
            <CesiumViewer
              building={building}
              floors={floors}
              units={units}
              selectedFloor={selectedFloor}
              selectedUlpin={unitDetail?.ulpin_3d}
              exploded={exploded}
              onSelectFloor={handleSelectFloor}
              onSelectUnit={handleSelectUnit}
            />
          </div>

          <div className="drawing-vignette" />
          <DrawingFurniture mode={view} />

          {view === 'plan' && !building && !missNote && (
            <p className="drawing-note">Select a parcel to issue its identifier</p>
          )}
          {view === 'plan' && missNote && (
            <p className="drawing-note is-warning">No parcel plotted here</p>
          )}
          {busy && <p className="drawing-busy">Issuing</p>}
        </div>

        <aside className="record">
          {error && (
            <div className="notice notice-error">
              <span className="notice-stamp">Error</span>
              <span>{error}</span>
            </div>
          )}

          <div className="notice">
            <span className="notice-stamp">Simulated</span>
            <span>
              Identifiers are generated for this prototype from OpenStreetMap
              geometry. They are not issued under DILRMP, and the ownership
              records are fabricated.
            </span>
          </div>

          {!building ? (
            <div className="empty-record">
              <h2>No parcel selected</h2>
              <p>
                Every building on the plan carries a 14-character parcel
                identifier. Selecting one slices it into levels and extends that
                code with a floor and room, issuing a full 18-character
                identifier for each room inside.
              </p>
              <ol className="empty-steps">
                {[
                  'Select a parcel on the plan',
                  'Read its levels in the axonometric',
                  'Open a unit for its ownership record',
                ].map((step, index) => (
                  <li key={step} style={{ '--i': index }}>
                    <b>{String(index + 1).padStart(2, '0')}</b> {step}
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <>
              <BuildingPanel building={building} />
              {floors.length > 0 && (
                <FloorSelector
                  floors={floors}
                  selectedFloor={selectedFloor}
                  onSelect={handleSelectFloor}
                />
              )}
              {units.length > 0 && (
                <UnitGrid
                  floorNumber={selectedFloor}
                  units={units}
                  selectedUlpin={unitDetail?.ulpin_3d}
                  onSelect={handleSelectUnit}
                />
              )}
              {unitDetail && <OwnershipCard unit={unitDetail} />}
            </>
          )}
        </aside>
      </main>
    </div>
  );
}
