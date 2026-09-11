import React, { useEffect, useRef } from 'react'
import { Map as MaplibreMap, NavigationControl, ScaleControl, Popup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { apiUrl } from './api.js'

function imageCoordinates(bounds) {
  const [w, s, e, n] = bounds
  return [[w, n], [e, n], [e, s], [w, s]]
}

export default function GeoEvidenceMap({ result }) {
  const host = useRef(null)
  const mapRef = useRef(null)
  const bounds = result?.map_context?.bounds_wgs84

  useEffect(() => {
    if (!host.current || !bounds || bounds.length !== 4) return undefined
    if (mapRef.current) {
      mapRef.current.remove()
      mapRef.current = null
    }

    const map = new MaplibreMap({
      container: host.current,
      center: [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2],
      zoom: 8,
      attributionControl: true,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [
          { id: 'background', type: 'background', paint: { 'background-color': '#e8eef5' } },
          { id: 'osm', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19, paint: { 'raster-opacity': 0.72 } },
        ],
      },
    })

    map.addControl(new NavigationControl({ visualizePitch: true }), 'top-right')
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-left')

    map.on('load', () => {
      if (result?.overlay_url) {
        map.addSource('analysis-overlay', {
          type: 'image',
          url: apiUrl(result.overlay_url),
          coordinates: imageCoordinates(bounds),
        })
        map.addLayer({
          id: 'analysis-overlay',
          type: 'raster',
          source: 'analysis-overlay',
          paint: { 'raster-opacity': 0.78 },
        })
      }

      const geojson = result?.geojson
      if (geojson?.features?.length) {
        map.addSource('evidence-polygons', { type: 'geojson', data: geojson })
        map.addLayer({
          id: 'evidence-fill',
          type: 'fill',
          source: 'evidence-polygons',
          paint: { 'fill-color': '#ef4444', 'fill-opacity': 0.30 },
        })
        map.addLayer({
          id: 'evidence-line',
          type: 'line',
          source: 'evidence-polygons',
          paint: { 'line-color': '#dc2626', 'line-width': 2 },
        })
        map.on('click', 'evidence-fill', (e) => {
          const f = e.features?.[0]
          if (!f) return
          const area = Number(f.properties?.area_m2 || 0)
          const html = `<strong>${f.properties?.class || 'Detected region'}</strong><br/>Area: ${(area / 1e6).toFixed(3)} km²`
          new Popup().setLngLat(e.lngLat).setHTML(html).addTo(map)
        })
        map.on('mouseenter', 'evidence-fill', () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', 'evidence-fill', () => { map.getCanvas().style.cursor = '' })
      }
      map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], { padding: 32, duration: 0 })
    })

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [result, bounds?.join(',')])

  if (!bounds) {
    return <div className="map-unavailable">Interactive map requires georeferenced imagery (GeoTIFF with CRS).</div>
  }
  return <div ref={host} className="geo-map" aria-label="Interactive evidence map" />
}
