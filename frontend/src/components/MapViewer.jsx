import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { INK } from '../theme';

const BENGALURU = { lon: 77.61, lat: 12.98, zoom: 13.2 };

/** A cadastral plan sheet, not a basemap: paper ground, hairline ink roads,
 *  no fills competing with the parcels. Street tiles need the network; the
 *  cached parcels are drawn over a paper background layer, so with the network
 *  down every clickable footprint still plots, just without streets beneath. */
const STYLE = {
  version: 8,
  glyphs: 'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf',
  sources: {
    openfreemap: { type: 'vector', url: 'https://tiles.openfreemap.org/planet' },
  },
  layers: [
    { id: 'paper', type: 'background', paint: { 'background-color': INK.paper1 } },
    {
      id: 'water',
      type: 'fill',
      source: 'openfreemap',
      'source-layer': 'water',
      paint: { 'fill-color': INK.paper2 },
    },
    {
      id: 'roads',
      type: 'line',
      source: 'openfreemap',
      'source-layer': 'transportation',
      paint: {
        'line-color': INK.line,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.4, 16, 1.4],
      },
    },
    {
      id: 'road-labels',
      type: 'symbol',
      source: 'openfreemap',
      'source-layer': 'transportation_name',
      layout: {
        'text-field': ['get', 'name'],
        'text-font': ['Noto Sans Regular'],
        'text-size': 10,
        'text-letter-spacing': 0.08,
        'symbol-placement': 'line',
      },
      paint: {
        'text-color': INK.ink3,
        'text-halo-color': INK.paper1,
        'text-halo-width': 1.4,
      },
    },
  ],
};

export default function MapViewer({ buildings, selectedOsmId, onSelectPoint }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const hoveredRef = useRef(null);
  // Held in a ref so the click handler, registered once, always calls the
  // current callback without needing to re-register.
  const onSelectRef = useRef(onSelectPoint);
  onSelectRef.current = onSelectPoint;

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [BENGALURU.lon, BENGALURU.lat],
      zoom: BENGALURU.zoom,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    // A real scale bar, driven by the map. A drawn-on one would be stating a
    // measurement it does not know.
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric', maxWidth: 110 }), 'bottom-left');

    map.on('load', () => {
      map.addSource('parcels', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        promoteId: 'osm_id',
      });

      map.addLayer({
        id: 'parcel-fill',
        type: 'fill',
        source: 'parcels',
        paint: {
          'fill-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], INK.accent,
            INK.ink1,
          ],
          'fill-opacity': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], 0.82,
            ['boolean', ['feature-state', 'hover'], false], 0.34,
            0.14,
          ],
        },
      });

      map.addLayer({
        id: 'parcel-outline',
        type: 'line',
        source: 'parcels',
        paint: {
          'line-color': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], INK.accent,
            INK.ink1,
          ],
          'line-width': [
            'case',
            ['boolean', ['feature-state', 'selected'], false], 1.8,
            0.9,
          ],
        },
      });

      map.on('click', (event) => {
        onSelectRef.current?.(event.lngLat.lat, event.lngLat.lng);
      });

      map.on('mousemove', 'parcel-fill', (event) => {
        map.getCanvas().style.cursor = 'pointer';
        const id = event.features?.[0]?.id;
        if (id === hoveredRef.current) return;
        if (hoveredRef.current != null) {
          map.setFeatureState({ source: 'parcels', id: hoveredRef.current }, { hover: false });
        }
        hoveredRef.current = id;
        map.setFeatureState({ source: 'parcels', id }, { hover: true });
      });

      map.on('mouseleave', 'parcel-fill', () => {
        map.getCanvas().style.cursor = '';
        if (hoveredRef.current != null) {
          map.setFeatureState({ source: 'parcels', id: hoveredRef.current }, { hover: false });
        }
        hoveredRef.current = null;
      });
    });

    return () => map.remove();
  }, []);

  // Plot the parcels once they arrive, and frame them: the cached sheet covers
  // a few square kilometres, so the opening view must land on it rather than
  // leaving the reader hunting for clickable footprints.
  const framedRef = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !buildings?.features?.length) return;

    const apply = () => {
      const source = map.getSource('parcels');
      if (!source) return;
      source.setData(buildings);

      if (framedRef.current) return;
      framedRef.current = true;

      const bounds = new maplibregl.LngLatBounds();
      for (const feature of buildings.features) {
        for (const [lon, lat] of feature.geometry.coordinates[0]) {
          bounds.extend([lon, lat]);
        }
      }
      map.fitBounds(bounds, { padding: 70, maxZoom: 16, duration: 0 });
    };

    if (map.isStyleLoaded() && map.getSource('parcels')) apply();
    else map.once('idle', apply);
  }, [buildings]);

  // Mirror the sheet's selection into the map's feature state.
  const previousSelection = useRef(null);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const apply = () => {
      if (!map.getSource('parcels')) return;
      if (previousSelection.current) {
        map.setFeatureState(
          { source: 'parcels', id: previousSelection.current },
          { selected: false },
        );
      }
      if (selectedOsmId) {
        map.setFeatureState({ source: 'parcels', id: selectedOsmId }, { selected: true });
      }
      previousSelection.current = selectedOsmId;
    };

    if (map.isStyleLoaded()) apply();
    else map.once('idle', apply);
  }, [selectedOsmId]);

  return <div ref={containerRef} className="map-canvas" />;
}
