import { useState, useEffect, useRef } from 'react'
import { getDashboardOverview } from '../services/api'
import Header from '../components/Header'
import {
  TrendingUp, AlertTriangle, Users, FolderOpen,
  ShieldAlert, Activity, CheckCircle, Clock, ArrowUp, ArrowDown
} from 'lucide-react'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Tooltip, Legend, Filler
} from 'chart.js'
import { Line, Doughnut, Bar } from 'react-chartjs-2'
import { useLanguage } from '../i18n/LanguageContext'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
  BarElement, ArcElement, Tooltip, Legend, Filler)

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const CRIME_COLORS = [
  '#C0392B','#E67E22','#F39C12','#2980B9','#8E44AD',
  '#16A085','#2C3E50','#D35400','#1ABC9C','#7F8C8D'
]

export default function Dashboard({ user }) {
  const { t, tv } = useLanguage()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getDashboardOverview()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const KPIS = data ? [
    { label: t('dashTotalFirs'), value: data.kpis.total_firs, icon: FolderOpen, color: 'blue', change: '+12%' },
    { label: t('dashOpenCases'), value: data.kpis.open_cases, icon: Clock, color: 'amber', change: '-3%' },
    { label: t('dashChargeSheeted'), value: data.kpis.charge_sheeted, icon: CheckCircle, color: 'green', change: '+8%' },
    { label: t('dashTotalAccused'), value: data.kpis.total_accused, icon: Users, color: 'blue', change: '' },
    { label: t('dashArrested'), value: data.kpis.arrested, icon: ShieldAlert, color: 'green', change: '+5%' },
    { label: t('dashHighRisk'), value: data.kpis.high_risk_offenders, icon: AlertTriangle, color: 'red', change: '' },
    { label: t('dashRepeatOffenders'), value: data.kpis.repeat_offenders, icon: Activity, color: 'amber', change: '' },
    { label: t('dashGangMembers'), value: data.kpis.gang_members, icon: TrendingUp, color: 'red', change: '' },
  ] : []

  const monthlyChartData = data ? (() => {
    const byMonth = {}
    data.monthly_trend_2024.forEach(r => { byMonth[parseInt(r.month)] = r.count })
    return {
      labels: MONTHS,
      datasets: [{
        label: 'Cases (2024)',
        data: MONTHS.map((_, i) => byMonth[i + 1] || 0),
        borderColor: '#C5A028',
        backgroundColor: 'rgba(197,160,40,0.08)',
        borderWidth: 2,
        pointBackgroundColor: '#C5A028',
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.4,
      }]
    }
  })() : null

  const doughnutData = data ? {
    labels: data.crime_distribution.map(d => d.crime_type),
    datasets: [{
      data: data.crime_distribution.map(d => d.count),
      backgroundColor: CRIME_COLORS,
      borderWidth: 0,
      hoverOffset: 6,
    }]
  } : null

  const districtData = data ? {
    labels: data.district_distribution.map(d => d.district.replace('Hubballi-Dharwad','Hubballi')),
    datasets: [{
      label: 'Cases',
      data: data.district_distribution.map(d => d.count),
      backgroundColor: 'rgba(11,29,58,0.8)',
      borderColor: '#C5A028',
      borderWidth: 1,
      borderRadius: 4,
    }]
  } : null

  const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { boxPadding: 4 } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#94A3B8' } },
      y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 11 }, color: '#94A3B8' } },
    }
  }

  const statusClass = s => {
    if (s === 'Under Investigation') return 'status-pill status-open'
    if (s === 'Charge-Sheeted') return 'status-pill status-sheeted'
    if (s === 'Closed') return 'status-pill status-closed'
    return 'status-pill status-filed'
  }

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748B' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: '3px solid #E2E8F0', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
        Loading intelligence data…
      </div>
    </div>
  )

  return (
    <>
      <Header title={t('navDashboard')} user={user} alerts={[1,2]} />
      <div className="page-content">
        {/* Alert banner — HONESTY FIX: this previously hardcoded a fabricated
            narrative ("Cybercrime up 34%... offender ACC-001 (Raju Kumar)
            released on bail") that wasn't derived from any real query — a
            specific, invented claim about a specific fictional person. It
            now reflects the dashboard's own real KPI numbers instead. */}
        {data && (data.kpis.high_risk_offenders > 0 || data.kpis.gang_members > 0) && (
          <div style={{
            background: 'linear-gradient(90deg, #7F1D1D 0%, #991B1B 100%)',
            borderRadius: 8, padding: '10px 16px', marginBottom: '1.25rem',
            display: 'flex', alignItems: 'center', gap: 10,
            animation: 'fadeIn 0.4s ease-out',
          }}>
            <AlertTriangle size={15} color="#FCA5A5" />
            <span style={{ fontSize: '0.78rem', color: '#FEE2E2', fontWeight: 500 }}>
              <strong style={{ color: '#FECACA' }}>{t('dashAlert')}</strong>{' '}
              {data.kpis.high_risk_offenders.toLocaleString('en-IN')} high-risk offender(s) and{' '}
              {data.kpis.gang_members.toLocaleString('en-IN')} gang-affiliated individual(s) currently on record —
              see Offender Profiles for details.
            </span>
          </div>
        )}

        {/* KPI Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
          {KPIS.map(kpi => (
            <div key={kpi.label} className={`kpi-card ${kpi.color}`} style={{ animation: 'fadeIn 0.4s ease-out' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
                <kpi.icon size={16} color={
                  kpi.color === 'red' ? '#C0392B' :
                  kpi.color === 'green' ? '#0F7A5A' :
                  kpi.color === 'amber' ? '#E67E22' : '#2563EB'
                } />
                {kpi.change && (
                  <span style={{
                    fontSize: '0.62rem', fontWeight: 600,
                    color: kpi.change.startsWith('+') ? '#065F46' : '#7F1D1D',
                    display: 'flex', alignItems: 'center', gap: 2,
                  }}>
                    {kpi.change.startsWith('+') ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                    {kpi.change}
                  </span>
                )}
              </div>
              <div className="kpi-value">{kpi.value?.toLocaleString('en-IN')}</div>
              <div className="kpi-label">{kpi.label}</div>
            </div>
          ))}
        </div>

        {/* Charts row */}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem', marginBottom: '1.25rem' }}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B' }}>{t('anaMonthlyTrend')} — 2024</div>
                <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginTop: 2 }}>{t('dashAllDistrictsCombined')}</div>
              </div>
              <span style={{ fontSize: '0.65rem', fontWeight: 600, background: '#FFF9DB', color: '#78350F', padding: '3px 8px', borderRadius: 4 }}>
                2024 YTD
              </span>
            </div>
            {monthlyChartData && <div style={{ height: 180 }}>
              <Line data={monthlyChartData} options={chartOpts} />
            </div>}
          </div>

          <div className="card">
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('dashCrimeTypeSplit')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>{t('dashDistributionAllFirs')}</div>
            {doughnutData && <div style={{ height: 140, display: 'flex', justifyContent: 'center' }}>
              <Doughnut data={doughnutData} options={{
                responsive: true, maintainAspectRatio: false,
                plugins: {
                  legend: { position: 'right', labels: { font: { size: 10 }, boxWidth: 10, padding: 8 } },
                  tooltip: { boxPadding: 4 }
                },
                cutout: '60%',
              }} />
            </div>}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
          {/* District bar chart */}
          <div className="card">
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B', marginBottom: 4 }}>{t('dashCasesByDistrict')}</div>
            <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginBottom: 12 }}>{t('dashTop8Districts')}</div>
            {districtData && <div style={{ height: 160 }}>
              <Bar data={districtData} options={{
                ...chartOpts,
                scales: {
                  x: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#94A3B8', maxRotation: 35 } },
                  y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 10 }, color: '#94A3B8' } },
                }
              }} />
            </div>}
          </div>

          {/* Recent FIRs */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '1rem 1.25rem 0.75rem', borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B' }}>{t('dashRecentFirs')}</div>
              <a href="/cases" style={{ fontSize: '0.68rem', color: '#2563EB', textDecoration: 'none', fontWeight: 600 }}>View All →</a>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t('dashFirNo')}</th>
                    <th>{t('district')}</th>
                    <th>{t('dashCrime')}</th>
                    <th>{t('status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.recent_firs || []).map(fir => (
                    <tr key={fir.fir_number}>
                      <td><span className="mono fir-no" style={{ fontSize: '0.7rem' }}>{fir.fir_number}</span></td>
                      <td style={{ fontSize: '0.75rem' }}>{tv(fir.district?.replace('Hubballi-Dharwad','Hubballi'))}</td>
                      <td style={{ fontSize: '0.75rem' }}>{tv(fir.crime_type)}</td>
                      <td><span className={statusClass(fir.status)}>{fir.status?.replace('Under Investigation','Investigating')}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
