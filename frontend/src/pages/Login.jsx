import { useState } from 'react'
import { Shield, Eye, EyeOff, AlertCircle, ChevronRight, UserPlus, Globe } from 'lucide-react'
import { login, register } from '../services/api'
import { useLanguage } from '../i18n/LanguageContext'

const DEMO_ACCOUNTS = [
  { username: 'investigator1', label: 'Inspector Ramesh Gowda', role: 'Investigator' },
  { username: 'analyst1',      label: 'Analyst Kavitha Shetty', role: 'Analyst' },
  { username: 'supervisor1',   label: 'SP Nagaraj Bhat',        role: 'Supervisor' },
  { username: 'admin',         label: 'DIG Vijay Desai',        role: 'Admin' },
]
const DEMO_PASSWORD = 'Kavach@2026'

export default function Login({ onLogin }) {
  const { language, toggleLanguage, t } = useLanguage()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('investigator')
  const [showPwd, setShowPwd] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleLogin(u = username, p = password) {
    if (!u || !p) { setError('Enter both username and password.'); return }
    setLoading(true); setError('')
    try {
      const data = await login(u, p)
      onLogin(data.user, data.token)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister() {
    if (!username || !password) { setError('Enter a username and password.'); return }
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setLoading(true); setError('')
    try {
      const data = await register(username, password, role)
      onLogin({ id: data.user.user_id, username: data.user.username, role: data.user.role,
                 full_name: username, badge_number: `KSP/${role.slice(0,3).toUpperCase()}/${data.user.user_id}`,
                 district: 'Unassigned' }, data.token)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <div style={{ width: '100%', maxWidth: 420 }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
          <button
            onClick={toggleLanguage}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 5, padding: '4px 12px', cursor: 'pointer',
              fontSize: '0.72rem', fontWeight: 600, color: '#C5A028',
            }}
          >
            <Globe size={12} />
            {language === 'en' ? 'ಕನ್ನಡಕ್ಕೆ ಬದಲಿಸಿ' : 'Switch to English'}
          </button>
        </div>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 68, height: 68, borderRadius: 16,
            background: 'linear-gradient(135deg, #C5A028 0%, #8A6E1A 100%)',
            marginBottom: '1rem', boxShadow: '0 8px 24px rgba(197,160,40,0.3)',
          }}>
            <Shield size={32} color="#fff" />
          </div>
          <h1 style={{ color: '#fff', fontSize: '1.6rem', fontWeight: 700, margin: '0 0 4px', letterSpacing: '-0.01em' }}>
            {t('loginTitle')}
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: '0.75rem', margin: 0, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
            {t('loginSubtitle')}
          </p>
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 12, padding: '1.75rem', backdropFilter: 'blur(10px)',
        }}>
          {/* Mode tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: '1.25rem', background: 'rgba(255,255,255,0.04)', borderRadius: 8, padding: 3 }}>
            {['login', 'register'].map(m => (
              <button key={m} onClick={() => { setMode(m); setError('') }} style={{
                flex: 1, padding: '7px', border: 'none', borderRadius: 6, cursor: 'pointer',
                fontSize: '0.78rem', fontWeight: 600, textTransform: 'capitalize',
                background: mode === m ? 'rgba(197,160,40,0.2)' : 'transparent',
                color: mode === m ? '#C5A028' : 'rgba(255,255,255,0.4)',
              }}>
                {m === 'login' ? t('loginButton') : t('loginRegisterButton')}
              </button>
            ))}
          </div>

          <div style={{ marginBottom: '0.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.5)', marginBottom: 6, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {mode === 'login' ? t('loginUsername') : 'Choose a Username'}
            </label>
            <input
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && (mode === 'login' ? handleLogin() : handleRegister())}
              placeholder={mode === 'login' ? 'e.g. investigator1' : 'e.g. officer_priya'}
              style={{
                width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#fff', fontSize: '0.85rem',
                outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.15s',
              }}
              onFocus={e => e.target.style.borderColor = '#C5A028'}
              onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.12)'}
            />
          </div>

          <div style={{ marginBottom: mode === 'register' ? '0.85rem' : '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.5)', marginBottom: 6, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {t('loginPassword')}
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (mode === 'login' ? handleLogin() : handleRegister())}
                placeholder={mode === 'login' ? 'Enter password' : 'At least 8 characters'}
                style={{
                  width: '100%', padding: '10px 40px 10px 14px', background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#fff', fontSize: '0.85rem',
                  outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.15s',
                }}
                onFocus={e => e.target.style.borderColor = '#C5A028'}
                onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.12)'}
              />
              <button onClick={() => setShowPwd(!showPwd)} style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.4)', display: 'flex',
              }}>
                {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {mode === 'register' && (
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.5)', marginBottom: 6, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                {t('loginRole')}
              </label>
              <select value={role} onChange={e => setRole(e.target.value)} style={{
                width: '100%', padding: '10px 14px', background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: '#fff', fontSize: '0.85rem',
                outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', cursor: 'pointer',
              }}>
                <option value="investigator" style={{ color: '#000' }}>Investigator</option>
                <option value="analyst" style={{ color: '#000' }}>Analyst</option>
                <option value="supervisor" style={{ color: '#000' }}>Supervisor</option>
              </select>
            </div>
          )}

          {error && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'rgba(192,57,43,0.15)', border: '1px solid rgba(192,57,43,0.3)',
              borderRadius: 6, padding: '8px 12px', marginBottom: '1rem', fontSize: '0.75rem', color: '#FCA5A5',
            }}>
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <button
            onClick={() => mode === 'login' ? handleLogin() : handleRegister()}
            disabled={loading || !username || !password}
            style={{
              width: '100%', padding: '11px',
              background: loading || !username || !password ? 'rgba(197,160,40,0.3)' : 'linear-gradient(135deg, #C5A028 0%, #A88420 100%)',
              border: 'none', borderRadius: 6, color: '#fff', fontSize: '0.85rem', fontWeight: 600,
              cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
              letterSpacing: '0.04em', transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}
          >
            {mode === 'register' && <UserPlus size={14} />}
            {loading ? t('loading') : mode === 'login' ? t('loginButton') : t('loginRegisterButton')}
          </button>
        </div>

        {mode === 'login' && (
          <div style={{ marginTop: '1.5rem' }}>
            <p style={{ textAlign: 'center', fontSize: '0.68rem', color: 'rgba(255,255,255,0.3)', marginBottom: '0.75rem', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              Demo Accounts — password: {DEMO_PASSWORD}
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {DEMO_ACCOUNTS.map(acc => (
                <button
                  key={acc.username}
                  onClick={() => handleLogin(acc.username, DEMO_PASSWORD)}
                  style={{
                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 8, padding: '10px 12px', cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                  }}
                  onMouseOver={e => { e.currentTarget.style.background = 'rgba(197,160,40,0.08)'; e.currentTarget.style.borderColor = 'rgba(197,160,40,0.3)' }}
                  onMouseOut={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: '0.6rem', fontWeight: 700, color: '#C5A028', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{acc.role}</span>
                    <ChevronRight size={10} color="rgba(255,255,255,0.3)" />
                  </div>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'rgba(255,255,255,0.8)', lineHeight: 1.3 }}>{acc.label}</div>
                  <div style={{ fontSize: '0.62rem', color: 'rgba(255,255,255,0.3)', marginTop: 2 }}>{acc.username}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        <p style={{ textAlign: 'center', fontSize: '0.62rem', color: 'rgba(255,255,255,0.2)', marginTop: '1.5rem', lineHeight: 1.6 }}>
          Passwords are bcrypt-hashed server-side. Sessions expire after 12 hours.<br />
          RESTRICTED SYSTEM — Authorised Personnel Only. All access is logged.
        </p>
      </div>
    </div>
  )
}
