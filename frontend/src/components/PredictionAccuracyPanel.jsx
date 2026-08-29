import { useState, useEffect } from 'react'
import { getPredictionAccuracy } from '../services/api'

const MONTHS_SHORT = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/*
  Prediction Accuracy Tracking (Feature 1): KAVACH's crime-trend
  forecasts, judged against what actually happened — see backend
  brain/prediction_tracking.py. This is "here is our historical
  performance" instead of "trust our prediction".
*/
export default function PredictionAccuracyPanel({ district = null }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    getPredictionAccuracy(district || null, null).then(setData).catch(() => setData(false))
  }, [district])

  if (data === null) return null
  if (data === false) return null

  const s = data.summary

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B' }}>Prediction Accuracy Record</div>
        {district && <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>{district}</span>}
      </div>
      <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 14 }}>
        How KAVACH's own crime-trend forecasts have actually performed, judged against real outcomes once they occurred
      </div>

      {s.settled_count === 0 ? (
        <p style={{ color: '#94A3B8', fontSize: '0.78rem' }}>
          No forecasts have reached their target month yet — an accuracy record builds up as predicted months
          become the actual past.
        </p>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 14 }}>
            <StatBox label="Settled Forecasts" value={s.settled_count} />
            <StatBox label="Direction Accuracy"
              value={s.direction_accuracy_pct !== null ? `${s.direction_accuracy_pct}%` : '—'} />
            <StatBox label="Within 20% of Actual"
              value={s.within_20_percent_pct !== null ? `${s.within_20_percent_pct}%` : '—'} />
            <StatBox label="Median Error" value={s.median_percent_error !== null ? `${s.median_percent_error}%` : '—'} />
          </div>

          {data.recent_predictions?.length > 0 && (
            <div style={{ maxHeight: 220, overflowY: 'auto', border: '1px solid #E2E8F0', borderRadius: 6 }}>
              <table style={{ width: '100%', fontSize: '0.68rem', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#F8FAFC', position: 'sticky', top: 0 }}>
                    {['District', 'Crime Type', 'Target', 'Predicted', 'Actual', 'Error'].map(h => (
                      <th key={h} style={{ textAlign: 'left', padding: '6px 8px', color: '#64748B', fontWeight: 700, borderBottom: '1px solid #E2E8F0' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.recent_predictions.slice(0, 15).map(p => (
                    <tr key={p.prediction_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '6px 8px', color: '#334155' }}>{p.district}</td>
                      <td style={{ padding: '6px 8px', color: '#334155' }}>{p.crime_type}</td>
                      <td style={{ padding: '6px 8px', color: '#334155' }}>{MONTHS_SHORT[p.target_month]} {p.target_year}</td>
                      <td style={{ padding: '6px 8px', color: '#334155' }}>{p.predicted_count?.toFixed(1)}</td>
                      <td style={{ padding: '6px 8px', color: '#334155' }}>
                        {p.actual_count !== null ? p.actual_count : <span style={{ color: '#CBD5E1' }}>pending</span>}
                      </td>
                      <td style={{ padding: '6px 8px' }}>
                        {p.percent_error !== null ? (
                          <span style={{ color: p.percent_error <= 20 ? '#16A34A' : p.percent_error <= 50 ? '#D97706' : '#C0392B', fontWeight: 700 }}>
                            {p.percent_error}%
                          </span>
                        ) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 10, fontSize: '0.62rem', color: '#94A3B8', lineHeight: 1.5 }}>
        {data.data_note}
      </div>
    </div>
  )
}

function StatBox({ label, value }) {
  return (
    <div style={{ padding: '10px 12px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6, textAlign: 'center' }}>
      <div style={{ fontSize: '1.3rem', fontWeight: 800, color: '#0B1D3A' }}>{value}</div>
      <div style={{ fontSize: '0.6rem', color: '#94A3B8', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
    </div>
  )
}
