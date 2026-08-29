import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, MessageSquare, Network, BarChart2,
  FolderOpen, Users, Shield, LogOut
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

// Nav items reference translation KEYS (not literal English strings) so
// the whole sidebar — not just the chat page — follows the language
// toggle in Header.jsx.
const NAV = [
  { section: 'Intelligence' },
  { to: '/',        icon: LayoutDashboard, labelKey: 'navDashboard', exact: true },
  { to: '/chat',    icon: MessageSquare,   labelKey: 'navChat',       badge: 'AI' },
  { to: '/network', icon: Network,         labelKey: 'navNetwork' },
  { section: 'Analytics' },
  { to: '/analytics',icon: BarChart2,      labelKey: 'navAnalytics' },
  { to: '/cases',   icon: FolderOpen,      labelKey: 'navCases' },
  { to: '/profiles',icon: Users,           labelKey: 'navProfiles' },
]

export default function Sidebar({ user, onLogout, loggingOut = false }) {
  const { t } = useLanguage()
  const initials = user?.full_name
    ? user.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
    : 'KSP'

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div style={{
          width: 34, height: 34, borderRadius: 6,
          background: 'linear-gradient(135deg, #C5A028 0%, #8A6E1A 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0
        }}>
          <Shield size={18} color="#fff" />
        </div>
        <div>
          <div className="logo-text">{t('appName')}</div>
          <div className="logo-sub">Karnataka State Police</div>
        </div>
      </div>

      {/* Online status */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '8px 16px',
        borderBottom: '1px solid rgba(197,160,40,0.1)',
      }}>
        <div style={{
          width: 7, height: 7, borderRadius: '50%',
          background: '#0F7A5A',
          boxShadow: '0 0 0 2px rgba(15,122,90,0.3)',
        }} />
        <span style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.4)', letterSpacing: '0.04em' }}>
          {t('secureConnection')} ● {t('online')}
        </span>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0' }}>
        {NAV.map((item, i) => {
          if (item.section) {
            return <div key={i} className="nav-section-label">{item.section}</div>
          }
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <item.icon size={15} className="nav-icon" />
              <span style={{ flex: 1 }}>{t(item.labelKey)}</span>
              {item.badge && (
                <span style={{
                  fontSize: '0.55rem', fontWeight: 700, letterSpacing: '0.06em',
                  background: 'rgba(197,160,40,0.2)', color: '#C5A028',
                  padding: '2px 6px', borderRadius: 3,
                }}>
                  {item.badge}
                </span>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom: User info */}
      <div style={{ borderTop: '1px solid rgba(197,160,40,0.15)', padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <div style={{
            width: 30, height: 30, borderRadius: '50%',
            background: 'rgba(197,160,40,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '0.72rem', fontWeight: 700, color: '#C5A028', flexShrink: 0
          }}>
            {initials}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'rgba(255,255,255,0.9)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.full_name || 'Officer'}
            </div>
            <div style={{ fontSize: '0.62rem', color: 'rgba(255,255,255,0.35)', textTransform: 'capitalize' }}>
              {user?.role} ● {user?.badge_number || 'KSP'}
            </div>
          </div>
        </div>
        <button
          onClick={onLogout}
          disabled={loggingOut}
          title={loggingOut ? 'Preparing your chat export before signing out…' : undefined}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: 8,
            background: 'rgba(192,57,43,0.1)', border: '1px solid rgba(192,57,43,0.2)',
            borderRadius: 5, padding: '6px 10px', cursor: loggingOut ? 'wait' : 'pointer',
            color: 'rgba(255,100,80,0.8)', fontSize: '0.72rem', fontWeight: 500,
            transition: 'all 0.15s', opacity: loggingOut ? 0.7 : 1,
          }}
          onMouseOver={e => e.currentTarget.style.background = 'rgba(192,57,43,0.2)'}
          onMouseOut={e => e.currentTarget.style.background = 'rgba(192,57,43,0.1)'}
        >
          <LogOut size={12} />
          {loggingOut ? 'Exporting chat & signing out…' : t('signOut')}
        </button>
      </div>
    </aside>
  )
}
