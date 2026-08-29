import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar   from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import CrimeChat from './pages/CrimeChat'
import Network   from './pages/Network'
import Analytics from './pages/Analytics'
import Cases     from './pages/Cases'
import Profiles  from './pages/Profiles'
import { validateSession, logout as apiLogout, exportChatHistoryPdf } from './services/api'
import { LanguageProvider } from './i18n/LanguageContext'
import LandingExperience from './landing/LandingExperience'
import { useGateStore } from './landing/store/gateStore'

/* -------------------------------------------------------------------------- */
/*  App shell                                                                  */
/* -------------------------------------------------------------------------- */
function AppShell({ user, onLogout, loggingOut }) {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar user={user} onLogout={onLogout} loggingOut={loggingOut} />
        <div className="main-area">
          <Routes>
            <Route path="/"         element={<Dashboard user={user} />} />
            <Route path="/chat"     element={<CrimeChat user={user} />} />
            <Route path="/network"  element={<Network   user={user} />} />
            <Route path="/analytics"element={<Analytics user={user} />} />
            <Route path="/cases"    element={<Cases     user={user} />} />
            <Route path="/profiles" element={<Profiles  user={user} />} />
            <Route path="*"         element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}

/* -------------------------------------------------------------------------- */
/*  Root                                                                       */
/* -------------------------------------------------------------------------- */
function AppRoot() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(true)
  const [loggingOut, setLoggingOut] = useState(false)
  // Gates the working app shell behind the cinematic entrance. A fresh
  // sign-in reaches this via the station hub (see handleEnterApp below);
  // a restored session skips straight past the entrance entirely, same
  // as the app already did before the entrance existed.
  const [showApp, setShowApp] = useState(false)

  // On mount: check for a stored token and validate it against the server
  // (not just trust whatever's sitting in storage — a revoked/expired
  // token should force a real re-login, same as any real auth system).
  useEffect(() => {
    const token = sessionStorage.getItem('kavach_token')
    const storedUser = sessionStorage.getItem('kavach_user')
    if (!token || !storedUser) { setChecking(false); return }

    validateSession(token)
      .then(() => {
        setUser(JSON.parse(storedUser))
        setShowApp(true)
      })
      .catch(() => {
        sessionStorage.removeItem('kavach_token')
        sessionStorage.removeItem('kavach_user')
      })
      .finally(() => setChecking(false))
  }, [])

  const handleLogin = (u, token) => {
    sessionStorage.setItem('kavach_user', JSON.stringify(u))
    sessionStorage.setItem('kavach_token', token)
    // A fresh login always starts a clean conversation — see
    // CrimeChat.jsx, which restores from this key on mount. Without
    // clearing it here, signing out and back in on the same shared
    // terminal would silently resume the previous officer's chat.
    sessionStorage.removeItem('kavach_active_chat_session')
    setUser(u)
  }

  // Fired when the officer picks a room in the station hub, after the
  // door-opening cutscene. Points the app shell's router at that room's
  // route before it ever mounts, so it opens straight there.
  const handleEnterApp = (route) => {
    window.history.replaceState(null, '', route)
    setShowApp(true)
  }

  // Automated export: right when an officer signs out, KAVACH bundles
  // every chat turn from THIS login into one PDF and downloads it
  // automatically — no separate "export" step for the officer to
  // remember. If the export fails for any reason (offline, server
  // hiccup), logout still proceeds — a broken export must never trap
  // someone in the app.
  const handleLogout = async () => {
    setLoggingOut(true)
    const token = sessionStorage.getItem('kavach_token')
    if (token) {
      try {
        const blob = await exportChatHistoryPdf('login')
        if (blob && blob.size > 0) {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `KAVACH-Chat-Export-${new Date().toISOString().slice(0, 10)}.pdf`
          document.body.appendChild(a)
          a.click()
          a.remove()
          URL.revokeObjectURL(url)
        }
      } catch (e) {
        console.error('Chat history export failed — signing out anyway:', e)
      }
      apiLogout(token).catch(() => {})  // revoke server-side session
    }
    sessionStorage.removeItem('kavach_user')
    sessionStorage.removeItem('kavach_token')
    sessionStorage.removeItem('kavach_active_chat_session')
    setUser(null)
    setLoggingOut(false)
    setShowApp(false)
    window.history.replaceState(null, '', '/')
    useGateStore.getState().reset()
  }

  if (checking) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#05101F' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: '3px solid rgba(255,255,255,0.1)', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite' }} />
      </div>
    )
  }

  if (!user || !showApp) {
    return <LandingExperience user={user} onLogin={handleLogin} onEnterApp={handleEnterApp} />
  }
  return <AppShell user={user} onLogout={handleLogout} loggingOut={loggingOut} />
}

export default function App() {
  return (
    <LanguageProvider>
      <AppRoot />
    </LanguageProvider>
  )
}
