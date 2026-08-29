import { useEffect, useRef, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.heat'
import { Flame, TrendingUp } from 'lucide-react'
import { getHotspots, getHotspotForecast } from '../services/api'

const KARNATAKA_CENTER = [15.3173, 75.7139]

// Small imperative bridge — leaflet.heat is a plain Leaflet plugin (not a
// React component), so it's added/removed on the live map instance via
// useMap(), inside an effect that re-runs whenever the point data changes.
function HeatLayer({ points }) {
  const map = useMap()
  const layerRef = useRef(null)

  useEffect(() => {
    if (layerRef.current) {
      map.removeLayer(layerRef.current)
      layerRef.current = null
    }
    if (points.length > 0) {
      layerRef.current = L.heatLayer(points, { radius: 32, blur: 24, maxZoom: 10 }).addTo(map)
    }
    return () => {
      if (layerRef.current) map.removeLayer(layerRef.current)
    }
  }, [map, points])

  return null
}

export default function HotspotMap() {
  const [mode, setMode] = useState('current') // 'current' | 'projected'
  const [current, setCurrent] = useState([])
  const [projected, setProjected] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    Promise.all([getHotspots(), getHotspotForecast(20)])
      .then(([cur, proj]) => {
        if (cancelled) return
        setCurrent(cur.hotspots || [])
        setProjected(proj.hotspots || [])
      })
      .catch(() => !cancelled && setError(true))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [])

  const rows = mode === 'current' ? current : projected
  const maxCount = Math.max(1, ...rows.map(r => r.case_count ?? r.predicted_count ?? 1))
  const points = rows
    .filter(r => (r.lat ?? r.latitude) && (r.lng ?? r.longitude))
    .map(r => {
      const lat = r.lat ?? r.latitude
      const lng = r.lng ?? r.longitude
      const weight = (r.case_count ?? r.predicted_count ?? 1) / maxCount
      return [lat, lng, weight]
    })

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 8, padding: '1rem', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Flame size={15} color="#C0392B" /> Crime Hotspot Map
        </div>
        <div style={{ display: 'flex', gap: 4, background: '#F8FAFC', borderRadius: 6, padding: 2, border: '1px solid #E2E8F0' }}>
          <button onClick={() => setMode('current')} style={{
            fontSize: '0.68rem', fontWeight: 600, padding: '4px 10px', borderRadius: 5, border: 'none',
            cursor: 'pointer', background: mode === 'current' ? '#0B1D3A' : 'transparent',
            color: mode === 'current' ? '#C5A028' : '#64748B',
          }}>
            Current
          </button>
          <button onClick={() => setMode('projected')} style={{
            fontSize: '0.68rem', fontWeight: 600, padding: '4px 10px', borderRadius: 5, border: 'none',
            cursor: 'pointer', background: mode === 'projected' ? '#0B1D3A' : 'transparent',
            color: mode === 'projected' ? '#C5A028' : '#64748B',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            <TrendingUp size={11} /> Projected, next 30 days
          </button>
        </div>
      </div>

      {mode === 'projected' && (
        <div style={{
          fontSize: '0.65rem', color: '#78350F', background: '#FFFBEB', border: '1px solid #FDE68A',
          borderRadius: 5, padding: '5px 9px', marginBottom: 8,
        }}>
          Statistical projection (trend + seasonal adjustment) over this project's own crime-trend history —
          not a machine-learning model, and not a guarantee. Presented as a planning aid only.
        </div>
      )}

      {loading ? (
        <div style={{ height: 380, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94A3B8', fontSize: '0.75rem' }}>
          Loading map data…
        </div>
      ) : error ? (
        <div style={{ height: 380, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#C0392B', fontSize: '0.75rem' }}>
          Couldn't load hotspot data.
        </div>
      ) : (
        <div style={{ height: 380, borderRadius: 6, overflow: 'hidden' }}>
          <MapContainer center={KARNATAKA_CENTER} zoom={7} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <HeatLayer points={points} />
            {rows.filter(r => (r.lat ?? r.latitude) && (r.lng ?? r.longitude)).slice(0, 20).map((r, i) => (
              <CircleMarker
                key={i}
                center={[r.lat ?? r.latitude, r.lng ?? r.longitude]}
                radius={4}
                pathOptions={{ color: '#0B1D3A', fillColor: '#C5A028', fillOpacity: 0.9, weight: 1 }}
              >
                <Tooltip direction="top">
                  <div style={{ fontSize: '0.7rem' }}>
                    <strong>{r.district}{r.police_station ? ` — ${r.police_station}` : ''}</strong><br />
                    {r.crime_type}<br />
                    {mode === 'current'
                      ? `${r.case_count} case(s) on file`
                      : `~${r.predicted_count} projected (${r.trend || 'trend n/a'}, ${r.confidence || 'n/a'} confidence)`}
                  </div>
                </Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      )}
    </div>
  )
}
