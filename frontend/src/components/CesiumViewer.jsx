import { useEffect, useRef } from 'react';
import {
  CallbackProperty,
  Cartesian2,
  Cartesian3,
  Color,
  HeadingPitchRange,
  HorizontalOrigin,
  Math as CesiumMath,
  OrthographicFrustum,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  VerticalOrigin,
  Viewer,
} from 'cesium';
import 'cesium/Build/Cesium/Widgets/widgets.css';
import { INK, unitWeight } from '../theme';

/** How far the levels travel apart, as a multiple of their stacked altitude. */
const EXPLODE_MAX = 2.4;
/** Fraction of the sequence spent staggering, so levels deal out bottom to top
 *  rather than all separating at once. */
const STAGGER_SPAN = 0.45;
const SEQUENCE_SECONDS = 1.1;

/** True isometric: the camera angles a drafter would set. */
const ISO_HEADING = CesiumMath.toRadians(45);
const ISO_PITCH = -Math.atan(Math.SQRT1_2); // ≈ -35.264°

const prefersReducedMotion = () =>
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

const easeOut = (t) => 1 - (1 - t) * (1 - t);
const clamp01 = (t) => Math.min(1, Math.max(0, t));

const ink = (alpha) => Color.fromCssColorString(INK.ink1).withAlpha(alpha);
const accent = (alpha) => Color.fromCssColorString(INK.accent).withAlpha(alpha);

/** No Cesium ion token is used anywhere here. The globe is switched off, so
 *  every polygon comes from our own cached geometry and the drawing plots
 *  offline.
 *
 *  The field is painted inside the scene rather than showing page CSS through
 *  a transparent canvas: a transparent WebGL surface composites Cesium's
 *  premultiplied output weakly over the page, draining every colour in the
 *  drawing. */
function createViewer(container) {
  const viewer = new Viewer(container, {
    baseLayer: false,
    baseLayerPicker: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    infoBox: false,
    selectionIndicator: false,
    creditContainer: document.createElement('div'),
  });

  const { scene } = viewer;
  scene.globe.show = false;
  scene.backgroundColor = Color.fromCssColorString(INK.field);
  scene.skyAtmosphere.show = false;
  scene.sun.show = false;
  scene.moon.show = false;
  if (scene.skyBox) scene.skyBox.show = false;

  // Orthographic projection — parallel lines stay parallel, which is what
  // makes this read as an axonometric drawing rather than a photograph.
  viewer.camera.frustum = new OrthographicFrustum({
    width: 400,
    aspectRatio: scene.canvas.clientWidth / Math.max(1, scene.canvas.clientHeight),
    near: 1,
    far: 1e6,
  });

  return viewer;
}

function ringToPositions(polygon) {
  // GeoJSON Polygon: coordinates[0] is the exterior ring of [lon, lat] pairs.
  return Cartesian3.fromDegreesArray(polygon.coordinates[0].flat());
}

/** The footprint's centre of extent and its furthest reach from there.
 *
 *  Deliberately not the polygon centroid: on an irregular outline the centroid
 *  sits away from the middle of the extent, and aiming the camera at it leaves
 *  the stack off-centre and clipped. Reach is measured from the ring rather
 *  than derived from the floor area, since a long thin slab of a building
 *  reaches much further than its area implies. */
function footprintFrame(building) {
  const ring = building.footprint.coordinates[0];
  const lons = ring.map(([lon]) => lon);
  const lats = ring.map(([, lat]) => lat);

  const lon = (Math.min(...lons) + Math.max(...lons)) / 2;
  const lat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const mPerDegLon = 111320 * Math.cos((lat * Math.PI) / 180);

  let reach = 0;
  for (const [pointLon, pointLat] of ring) {
    reach = Math.max(
      reach,
      Math.hypot((pointLon - lon) * mPerDegLon, (pointLat - lat) * 110540),
    );
  }
  return { lat, lon, reach };
}

export default function CesiumViewer({
  building,
  floors,
  units,
  selectedFloor,
  selectedUlpin,
  exploded,
  onSelectFloor,
  onSelectUnit,
}) {
  const containerRef = useRef(null);
  const viewerRef = useRef(null);
  // Sequence progress, 0 (assembled) to 1 (fully exploded). Held in a ref and
  // read by CallbackProperties, so the animation never re-renders React.
  const progressRef = useRef(1);
  const targetRef = useRef(1);
  const handlersRef = useRef({});

  handlersRef.current.onSelectFloor = onSelectFloor;
  handlersRef.current.onSelectUnit = onSelectUnit;

  useEffect(() => {
    const viewer = createViewer(containerRef.current);
    viewerRef.current = viewer;

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction((movement) => {
      const entity = viewer.scene.pick(movement.position)?.id;
      if (!entity) return;
      if (entity.ulpin3d) handlersRef.current.onSelectUnit?.(entity.ulpin3d);
      else if (entity.floorNumber != null) handlersRef.current.onSelectFloor?.(entity.floorNumber);
    }, ScreenSpaceEventType.LEFT_CLICK);

    const stopTick = viewer.clock.onTick.addEventListener(() => {
      const delta = targetRef.current - progressRef.current;
      if (Math.abs(delta) < 0.002) {
        progressRef.current = targetRef.current;
        return;
      }
      const step = prefersReducedMotion() ? 1 : 1 / (SEQUENCE_SECONDS * 60);
      progressRef.current += Math.sign(delta) * Math.min(Math.abs(delta), step);
    });

    return () => {
      stopTick();
      handler.destroy();
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  useEffect(() => {
    targetRef.current = exploded ? 1 : 0;
  }, [exploded]);

  // Redraw whenever the parcel, its levels, or the selection change.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return;

    viewer.entities.removeAll();
    if (!building || !floors?.length) return;

    const positions = ringToPositions(building.footprint);
    const floorHeight = building.floor_height;
    const lastIndex = Math.max(1, floors.length - 1);

    /** Each level runs the same ramp, offset by its height in the stack. */
    const spreadFor = (index) => {
      const delay = (index / lastIndex) * STAGGER_SPAN;
      const local = clamp01((progressRef.current - delay) / (1 - STAGGER_SPAN));
      return 1 + (EXPLODE_MAX - 1) * easeOut(local);
    };

    // Slabs thin slightly as they separate, so the gaps read as gaps.
    const thickness = (index) =>
      floorHeight * (1 - 0.2 * ((spreadFor(index) - 1) / (EXPLODE_MAX - 1)));

    // Cast shadow on the ground plane: without the globe there is nothing for
    // the stack to sit on, and it floats.
    viewer.entities.add({
      polygon: {
        hierarchy: positions,
        material: ink(0.2),
        height: 0,
      },
    });
    viewer.entities.add({
      polygon: {
        hierarchy: positions,
        material: Color.TRANSPARENT,
        outline: true,
        outlineColor: ink(0.65),
        height: 0,
      },
    });

    floors.forEach((floor, index) => {
      const base = () => floor.base_z * spreadFor(index);
      const isSelected = floor.floor_number === selectedFloor;

      // The selected level is drawn as its individual units; the rest stay
      // single slabs so the drawing keeps one subject.
      if (isSelected && units?.length) {
        for (const unit of units) {
          const highlighted = unit.ulpin_3d === selectedUlpin;
          // One accent throughout; the use is carried by fill strength, and
          // spelled out by hatch in the schedule beside the drawing.
          const fill = highlighted ? 0.92 : unitWeight(unit.unit_type);
          // A highlighted unit lifts clear of its level, like a callout
          // pulling the piece out of an assembly drawing.
          const lift = () => (highlighted ? thickness(index) * 0.6 : 0);

          const entity = viewer.entities.add({
            polygon: {
              hierarchy: ringToPositions(unit.polygon),
              material: accent(fill),
              outline: true,
              outlineColor: highlighted ? ink(0.95) : accent(0.9),
              height: new CallbackProperty(() => base() + lift(), false),
              extrudedHeight: new CallbackProperty(
                () => base() + lift() + thickness(index),
                false,
              ),
            },
          });
          entity.ulpin3d = unit.ulpin_3d;
          entity.floorNumber = floor.floor_number;
        }
        return;
      }

      // Barely filled, firmly outlined: eighteen translucent slabs stacked in
      // depth turn to grey mush, whereas linework stays readable.
      // Near-transparent fill, strong outline. Any real opacity here compounds
      // across eighteen stacked slabs into a solid blob that hides the
      // linework carrying the drawing.
      const entity = viewer.entities.add({
        polygon: {
          hierarchy: positions,
          material: Color.fromCssColorString(INK.paper0).withAlpha(0.07),
          outline: true,
          outlineColor: ink(0.85),
          height: new CallbackProperty(base, false),
          extrudedHeight: new CallbackProperty(() => base() + thickness(index), false),
        },
      });
      entity.floorNumber = floor.floor_number;
    });

    // Callout for the level pulled out of the assembly: a leader running clear
    // of the stack to a label, the way an exploded drawing annotates the piece
    // it has separated.
    const selected = floors.find((floor) => floor.floor_number === selectedFloor);
    if (selected) {
      const { lat, lon, reach } = footprintFrame(building);
      const leaderEndLon =
        lon + (reach * 1.25) / (111320 * Math.cos((lat * Math.PI) / 180));
      const index = floors.indexOf(selected);
      const calloutZ = () => selected.base_z * spreadFor(index) + thickness(index) / 2;

      viewer.entities.add({
        polyline: {
          positions: new CallbackProperty(
            () => [
              Cartesian3.fromDegrees(lon, lat, calloutZ()),
              Cartesian3.fromDegrees(leaderEndLon, lat, calloutZ()),
            ],
            false,
          ),
          width: 1,
          material: accent(0.75),
        },
      });

      viewer.entities.add({
        position: new CallbackProperty(
          () => Cartesian3.fromDegrees(leaderEndLon, lat, calloutZ()),
          false,
        ),
        label: {
          text: `${selected.floor_number === 0 ? 'GND' : `L${String(selected.floor_number).padStart(2, '0')}`}  ${selected.unit_count} UNITS`,
          font: '500 12px "JetBrains Mono", monospace',
          fillColor: Color.fromCssColorString(INK.ink1),
          showBackground: false,
          horizontalOrigin: HorizontalOrigin.LEFT,
          verticalOrigin: VerticalOrigin.CENTER,
          pixelOffset: new Cartesian2(8, 0),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
      });
    }
  }, [building, floors, units, selectedFloor, selectedUlpin]);

  // Frame the stack. Under an orthographic frustum the on-screen size is set
  // by the frustum width, not by camera distance, so the two are set apart.
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed() || !building) return;

    const frame = () => {
      const { scene, camera } = viewer;
      const { lat, lon, reach } = footprintFrame(building);
      const stackHeight = building.total_height * (exploded ? EXPLODE_MAX : 1);
      // Sphere enclosing the whole stack: half its height, and the footprint's
      // furthest reach, are perpendicular.
      const radius = Math.max(30, Math.hypot(reach, stackHeight / 2));

      const aspect = scene.canvas.clientWidth / Math.max(1, scene.canvas.clientHeight);

      camera.lookAt(
        Cartesian3.fromDegrees(lon, lat, stackHeight / 2),
        // Distance only has to clear the near plane under orthographic.
        new HeadingPitchRange(ISO_HEADING, ISO_PITCH, Math.max(600, radius * 8)),
      );

      // Must follow lookAt: under an orthographic frustum Cesium treats the
      // range as the zoom and overwrites `width` with it, so fitting the
      // drawing before the camera move would be discarded.
      if (camera.frustum instanceof OrthographicFrustum) {
        camera.frustum.aspectRatio = aspect;
        // Fit the stack on whichever axis is tighter, plus a margin.
        camera.frustum.width = 2 * radius * 1.18 * Math.max(1, aspect);
      }
    };

    frame();

    // Keep the drawing fitted when the sheet is resized.
    const observer = new ResizeObserver(frame);
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [building?.osm_id, exploded]);

  return <div ref={containerRef} className="map-canvas cesium-canvas" />;
}
