import { useState, useEffect } from 'react'
import { getCrimeTrends, getDemographics, getDistrictSummary } from '../services/api'
import Header from '../components/Header'
import HotspotMap from '../components/HotspotMap'
import PredictionAccuracyPanel from '../components/PredictionAccuracyPanel'
import { Line, Bar, Doughnut, Radar } from 'react-chartjs-2'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, RadialLinearScale, Tooltip, Legend, Filler
} from 'chart.js'
import { useLanguage } from '../i18n/LanguageContext'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, RadialLinearScale, Tooltip, Legend, Filler)

const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const CRIME_COLORS = ['#C0392B','#E67E22','#F39C12','#2980B9','#8E44AD','#16A085','#2C3E50','#D35400']
const GRID = { color: '#F1F5F9' }
const TICK = { font: { size: 10 }, color: '#94A3B8' }

export default function Analytics({ user }) {
  const { t, tv } = useLanguage()
  const [trends, setTrends] = useState(null)
  const [demographics, setDemographics] = useState(null)
  const [districtSummary, setDistrictSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedYear, setSelectedYear] = useState(2024)
  const [selectedDistrict, setSelectedDistrict] = useState('')

  useEffect(() => {
    Promise.all([
      getCrimeTrends({ year: selectedYear, district: selectedDistrict || undefined }),
      getDemographics(),
      getDistrictSummary(),
    ])
      .then(([t, d, ds]) => { setTrends(t); setDemographics(d); setDistrictSummary(ds) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [selectedYear, selectedDistrict])

  const monthlyLineData = trends ? (() => {
    const byMonth = {}
    trends.monthly.forEach(r => {
      const key = `${r.year}-${String(r.month).padStart(2,'0')}`
      byMonth[r.month] = (byMonth[r.month] || 0) + r.cases
    })
    return {
      labels: MONTHS_SHORT,
      datasets: [{
        label: `Cases ${selectedYear}`,
        data: MONTHS_SHORT.map((_, i) => byMonth[i + 1] || 0),
        borderColor: '#C5A028', backgroundColor: 'rgba(197,160,40,0.08)',
        borderWidth: 2, pointRadius: 4, fill: true, tension: 0.4,
        pointBackgroundColor: '#C5A028',
      }]
    }
  })() : null

  const crimeTypeData = trends ? {
    labels: trends.by_crime_type.map(r => r.crime_type),
    datasets: [{
      data: trends.by_crime_type.map(r => r.total),
      backgroundColor: CRIME_COLORS, borderWidth: 0, hoverOffset: 8,
    }]
  } : null

  const genderData = demographics ? {
    labels: demographics.gender_distribution.map(g => g.gender === 'M' ? 'Male' : 'Female'),
    datasets: [{
      data: demographics.gender_distribution.map(g => g.count),
      backgroundColor: ['#2563EB','#EC4899'], borderWidth: 0,
    }]
  } : null

  const educationData = demographics ? {
    labels: demographics.education_distribution.map(e => e.education),
    datasets: [{
      label: 'Accused Count',
      data: demographics.education_distribution.map(e => e.count),
      backgroundColor: 'rgba(11,29,58,0.8)', borderColor: '#C5A028', borderWidth: 1, borderRadius: 4,
    }]
  } : null

  const districtBarData = districtSummary ? {
    labels: districtSummary.districts.slice(0,8).map(d => d.district.replace('Hubballi-Dharwad','Hubballi')),
    datasets: [
      { label: 'Open Cases', data: districtSummary.districts.slice(0,8).map(d => d.open_cases), backgroundColor: '#E67E22', borderRadius: 3, stack: 'a' },
      { label: 'Charge-Sheeted', data: districtSummary.districts.slice(0,8).map(d => d.charge_sheeted), backgroundColor: '#8E44AD', borderRadius: 3, stack: 'a' },
      { label: 'Closed', data: districtSummary.districts.slice(0,8).map(d => d.closed), backgroundColor: '#0F7A5A', borderRadius: 3, stack: 'a' },
    ]
  } : null

  const occData = demographics ? {
    labels: demographics.top_occupations.slice(0,8).map(o => o.occupation),
    datasets: [{
      label: 'Count',
      data: demographics.top_occupations.slice(0,8).map(o => o.count),
      backgroundColor: 'rgba(197,160,40,0.7)', borderColor: '#C5A028', borderWidth: 1, borderRadius: 4,
    }]
  } : null

  const baseOpts = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { boxPadding: 4 } } }
  const axisOpts = { ...baseOpts, scales: { x: { grid: { display: false }, ticks: TICK }, y: { grid: GRID, ticks: TICK } } }

  // HONESTY FIX: this panel previously hardcoded four fabricated
  // statistics ("Theft spikes 38% in Oct-Nov", "Cybercrime rose 34%
  // YoY", "4 organised gangs... cross-border operations detected", etc.)
  // that were never derived from the trends/demographics/districtSummary
  // data actually being fetched above — invented numbers presented as
  // real analysis. Every insight below is now computed directly from
  // that same fetched data, with nothing stated that isn't in it.
  const insights = (trends && demographics && districtSummary) ? [
    trends.by_crime_type?.length > 0 && {
      title: 'Most Common Crime Type', color: '#C0392B',
      text: `"${trends.by_crime_type[0].crime_type}" accounts for ${trends.by_crime_type[0].total.toLocaleString('en-IN')} case(s) in ${selectedYear} — the highest of any category shown.`,
    },
    districtSummary.districts?.length > 0 && (() => {
      const top = [...districtSummary.districts].sort((a, b) =>
        (b.open_cases + b.charge_sheeted + b.closed) - (a.open_cases + a.charge_sheeted + a.closed))[0]
      return {
        title: 'Highest-Volume District', color: '#F39C12',
        text: `${top.district} has the highest combined case count among the districts shown here.`,
      }
    })(),
    demographics.top_occupations?.length > 0 && {
      title: 'Most Common Occupation Among Accused', color: '#8E44AD',
      text: `"${demographics.top_occupations[0].occupation}" is the most frequently recorded occupation among accused persons on record (${demographics.top_occupations[0].count.toLocaleString('en-IN')} individual(s)).`,
    },
    demographics.gender_distribution?.length > 0 && (() => {
      const total = demographics.gender_distribution.reduce((s, g) => s + g.count, 0)
      const top = [...demographics.gender_distribution].sort((a, b) => b.count - a.count)[0]
      const pct = total ? Math.round((top.count / total) * 100) : 0
      const label = top.gender === 'M' ? 'male' : top.gender === 'F' ? 'female' : top.gender
      return { title: 'Gender Distribution', color: '#2980B9', text: `${pct}% of accused persons on record are ${label}.` }
    })(),
  ].filter(Boolean) : []

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748B' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: '3px solid #E2E8F0', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
        Loading analytics…
      </div>
    </div>
  )

  return (
    <>
      <Header title={t('navAnalytics')} subtitle="Trends, Patterns & Sociological Insights" user={user} />
      <div className="page-content">
        {/* Filters */}
        <div style={{ display: 'flex', gap: 10, marginBottom: '1.25rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 600 }}>{t('anaFilterLabel')}</span>
          {[2020, 2021, 2022, 2023, 2024].map(y => (
            <button key={y} onClick={() => setSelectedYear(y)} style={{
              padding: '4px 12px', fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
              borderRadius: 5, border: `1px solid ${selectedYear === y ? '#0B1D3A' : '#E2E8F0'}`,
              background: selectedYear === y ? '#0B1D3A' : '#fff',
              color: selectedYear === y ? '#C5A028' : '#64748B',
            }}>
              {y}
            </button>
          ))}
          <select
            value={selectedDistrict}
            onChange={e => setSelectedDistrict(e.target.value)}
            style={{
              padding: '4px 10px', fontSize: '0.72rem', borderRadius: 5,
              border: '1px solid #E2E8F0', background: '#fff', color: '#475569',
              cursor: 'pointer', outline: 'none',
            }}
          >
            <option value="">{t('anaAllDistricts')}</option>
            {districtSummary?.districts.map(d => (
              <option key={d.district} value={d.district}>{d.district}</option>
            ))}
          </select>
        </div>

        {/* Row 1: Monthly trend + Crime split */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B' }}>{t('anaMonthlyTrend')}</div>
                <div style={{ fontSize: '0.68rem', color: '#94A3B8' }}>All registered cases — {selectedYear}</div>
              </div>
            </div>
            {monthlyLineData && <div style={{ height: 200 }}><Line data={monthlyLineData} options={axisOpts} /></div>}
          </div>

          <div className="card">
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('anaCrimeTypeDistribution')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>{selectedYear}</div>
            {crimeTypeData && <div style={{ height: 160 }}>
              <Doughnut data={crimeTypeData} options={{
                ...baseOpts, cutout: '55%',
                plugins: {
                  legend: { position: 'right', labels: { font: { size: 9 }, boxWidth: 10, padding: 6 } },
                  tooltip: { boxPadding: 4 }
                }
              }} />
            </div>}
          </div>
        </div>

        {/* Row 2: Interactive hotspot map (replaces the district bar chart —
            same underlying geographic story, now plotted on an actual map
            with a Current / Projected-next-30-days toggle) + Occupation */}
        <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <HotspotMap />

          <div className="card">
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('anaTopOccupations')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>{t('anaSocioEconomic')}</div>
            {occData && <div style={{ height: 200 }}>
              <Bar data={occData} options={{
                ...baseOpts, indexAxis: 'y',
                scales: {
                  x: { grid: GRID, ticks: TICK },
                  y: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#64748B' } },
                }
              }} />
            </div>}
          </div>
        </div>

        {/* Row 3: Gender + Education */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
          <div className="card">
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('anaGenderDistribution')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>{t('anaAmongAllAccused')}</div>
            {genderData && <div style={{ height: 180, display: 'flex', justifyContent: 'center' }}>
              <Doughnut data={genderData} options={{
                ...baseOpts, cutout: '50%',
                plugins: {
                  legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12, padding: 10 } },
                  tooltip: { boxPadding: 4 }
                }
              }} />
            </div>}
          </div>

          <div className="card">
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('anaEducationLevel')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>Educational background of accused persons on record</div>
            {educationData && <div style={{ height: 180 }}>
              <Bar data={educationData} options={axisOpts} />
            </div>}
          </div>
        </div>

        <PredictionAccuracyPanel district={selectedDistrict || null} />

        {/* Insights panel — now genuinely computed from the fetched data (see `insights` above) */}
        {insights.length > 0 && (
          <div className="card" style={{ background: 'linear-gradient(135deg, #0B1D3A 0%, #1A3360 100%)', border: 'none' }}>
            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#C5A028', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              ⚡ KAVACH Analytical Insights
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
              {insights.map(ins => (
                <div key={ins.title} style={{
                  background: 'rgba(255,255,255,0.04)', borderRadius: 8,
                  padding: '12px 14px', border: `1px solid ${ins.color}33`,
                  borderLeft: `3px solid ${ins.color}`,
                }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 700, color: ins.color, marginBottom: 5 }}>{ins.title}</div>
                  <div style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.7)', lineHeight: 1.55 }}>{ins.text}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  )
}
