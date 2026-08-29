import { Bell, Globe, ChevronRight } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useLanguage } from '../i18n/LanguageContext'

// Language now comes from the shared LanguageContext instead of being
// passed in per-page — previously only CrimeChat.jsx wired up a
// language/onLanguageToggle prop pair on this component, so every other
// page (Dashboard, Analytics, Cases, Profiles, Network) never even
// showed the toggle button. Now every page that renders <Header> gets
// the same toggle, backed by the same global state, automatically.
export default function Header({ title, subtitle, user, alerts = [] }) {
  const [time, setTime] = useState(new Date())
  const { language, toggleLanguage, t } = useLanguage()

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const fmt = tm => tm.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  const fmtDate = tm => tm.toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <header className="top-header">
      {/* Breadcrumb */}
      <div style={{ flex: 1 }}>
        <div className="header-breadcrumb">
          <span style={{ color: '#94A3B8', fontWeight: 400 }}>KSP / SCRB</span>
          <ChevronRight size={12} style={{ display: 'inline', margin: '0 4px', color: '#CBD5E1' }} />
          <span>{title}</span>
          {subtitle && (
            <>
              <ChevronRight size={12} style={{ display: 'inline', margin: '0 4px', color: '#CBD5E1' }} />
              <span style={{ color: '#64748B', fontWeight: 400 }}>{subtitle}</span>
            </>
          )}
        </div>
      </div>

      {/* Right controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        {/* Clock */}
        <div style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: '0.72rem',
          color: '#64748B',
          textAlign: 'right',
          lineHeight: 1.4,
        }}>
          <div style={{ fontWeight: 600, color: '#334155' }}>{fmt(time)}</div>
          <div style={{ fontSize: '0.62rem' }}>{fmtDate(time)}</div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 28, background: '#E2E8F0' }} />

        {/* Language toggle — applies app-wide now, not just to this page */}
        <button
          onClick={toggleLanguage}
          title={language === 'en' ? 'Switch to Kannada' : 'Switch to English'}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: language === 'kn' ? '#0B1D3A' : '#F8FAFC',
            border: `1px solid ${language === 'kn' ? '#C5A028' : '#E2E8F0'}`,
            borderRadius: 5, padding: '4px 10px', cursor: 'pointer',
            fontSize: '0.72rem', fontWeight: 600,
            color: language === 'kn' ? '#C5A028' : '#475569',
            transition: 'all 0.15s',
          }}
        >
          <Globe size={12} />
          {language === 'en' ? 'EN' : 'ಕನ್ನಡ'}
        </button>

        {/* Alerts bell */}
        <div style={{ position: 'relative' }}>
          <button style={{
            background: 'none', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', padding: 4,
            color: '#64748B',
          }}>
            <Bell size={16} />
          </button>
          {alerts.length > 0 && (
            <span style={{
              position: 'absolute', top: 0, right: 0,
              width: 14, height: 14, borderRadius: '50%',
              background: '#C0392B', color: '#fff',
              fontSize: '0.55rem', fontWeight: 700,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              {alerts.length}
            </span>
          )}
        </div>

        {/* Divider */}
        <div style={{ width: 1, height: 28, background: '#E2E8F0' }} />

        {/* User badge */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '4px 10px',
          background: '#F8FAFC',
          border: '1px solid #E2E8F0',
          borderRadius: 6,
        }}>
          <div style={{
            width: 24, height: 24, borderRadius: '50%',
            background: '#0B1D3A',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.6rem', fontWeight: 700, color: '#C5A028',
          }}>
            {user?.full_name?.split(' ').map(w => w[0]).join('').slice(0, 2) || 'KS'}
          </div>
          <div>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#1E293B', lineHeight: 1.2 }}>
              {user?.full_name?.split(' ').slice(0, 2).join(' ') || 'Officer'}
            </div>
            <div style={{ fontSize: '0.6rem', color: '#94A3B8', textTransform: 'capitalize' }}>
              {user?.role}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
