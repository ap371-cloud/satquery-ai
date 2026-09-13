import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Map as MaplibreMap, NavigationControl, ScaleControl, Popup } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { apiUrl } from './api.js'

function imageCoordinates(bounds) {
  const [w, s, e, n] = bounds
  return [[w, n], [e, n], [e, s], [w, s]]
}

const PALETTE = ['#ef4444', '#3b82f6', '#8b5cf6', '#22c55e', '#f59e0b', '#ec4899', '#14b8a6', '#84cc16']
const normalize = (s = '') => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '')

function classLabel(cls) {
  return cls.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function GeoEvidenceMap({ result }) {
  const host = useRef(null)
  const mapRef = useRef(null)
  const bounds = result?.map_context?.bounds_wgs84
  const legend = result?.legend || []

  const layers = useMemo(() => {
    const raw = result?.geojson_layers
    const entries = Object.entries(raw || {})
    if (entries.length === 0 && result?.geojson?.features?.length) {
      return [{ key: 'probable_new_inundation', label: 'Probable new inundation', color: '#ef4444', features: result.geojson.features.length }]
    }
    return entries.filter(([, g]) => g?.features?.length).map(([key, g], i) => {
      const legendEntry = legend.find(l => normalize(l.label) === normalize(key) || normalize(l.label) === normalize(classLabel(key)))
      return { key, label: legendEntry?.label || classLabel(key), color: legendEntry?.color || PALETTE[i % PALETTE.length], features: g.features.length }
    })
  }, [result, legend])

  const [visible, setVisible] = useState({})
  useEffect(() => {
    setVisible(Object.fromEntries(layers.map(l => [l.key, true])))
  }, [result?.geojson_layers, result?.geojson, layers])

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
      if (layers.length === 0 && result?.overlay_url) {
        map.addSource('analysis-overlay', {
          type: 'image',
          url: apiUrl(result.overlay_url),
          coordinates: imageCoordinates(bounds),
        })
        map.addLayer({ id: 'analysis-overlay', type: 'raster', source: 'analysis-overlay', paint: { 'raster-opacity': 0.78 } })
      }

      const seen = new Set()
      layers.forEach(l => {
        if (visible[l.key] === false) return
        if (seen.has(l.key)) return
        seen.add(l.key)
        const geojson = result?.geojson_layers?.[l.key] || result?.geojson
        if (!geojson?.features?.length) return
        const fillId = `layer-${l.key}-fill`
        const lineId = `layer-${l.key}-line`
        map.addSource(fillId, { type: 'geojson', data: geojson })
        map.addLayer({ id: fillId, type: 'fill', source: fillId, paint: { 'fill-color': l.color, 'fill-opacity': 0.30 } })
        map.addLayer({ id: lineId, type: 'line', source: fillId, paint: { 'line-color': l.color, 'line-width': 2 } })
        map.on('click', fillId, (e) => {
          const f = e.features?.[0]
          if (!f) return
          const area = Number(f.properties?.area_m2 || 0)
          const html = `<strong>${f.properties?.class ? classLabel(f.properties.class) : l.label}</strong><br/>Area: ${(area / 1e6).toFixed(3)} km²`
          new Popup().setLngLat(e.lngLat).setHTML(html).addTo(map)
        })
        map.on('mouseenter', fillId, () => { map.getCanvas().style.cursor = 'pointer' })
        map.on('mouseleave', fillId, () => { map.getCanvas().style.cursor = '' })
      })
      map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], { padding: 32, duration: 0 })
    })

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [result, bounds?.join(','), layers, visible])

  if (!bounds) {
    return <div className="map-unavailable">Interactive map requires georeferenced imagery (GeoTIFF with CRS).</div>
  }
  return (
    <div className="geo-map-wrap">
      {layers.length > 0 && (
        <div className="map-layers">
          {layers.map(l => {
            const on = visible[l.key] !== false
            return (
              <button
                key={l.key}
                className={`layer-chip${on ? ' active' : ''}`}
                onClick={() => setVisible(v => ({ ...v, [l.key]: !on }))}
                title={`${l.features} vector feature(s)`}
                type="button"
              >
                <i style={{ background: on ? l.color : '#cbd5e1' }} />
                <span>{l.label}</span>
                <small>{l.features}</small>
              </button>
            )
          })}
        </div>
      )}
      <div ref={host} className="geo-map" aria-label="Interactive evidence map" />
    </div>
  )
}