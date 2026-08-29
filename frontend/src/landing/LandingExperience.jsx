import { useEffect, useRef, useState } from 'react'
import Preloader from './components/Preloader'
import StationBackdrop from './components/StationBackdrop'
import ScrollOverlays from './components/ScrollOverlays'
import EntryGate from './components/EntryGate'
import LoginReveal from './components/LoginReveal'
import StationHub from './components/StationHub'
import { useScrollController } from './hooks/useScrollController'
import { useGateTransition } from './hooks/useGateTransition'
import { useDoorCutscene } from './hooks/useDoorCutscene'
import { useGateStore } from './store/gateStore'
import './landing.css'

/**
 * The cinematic front door of KAVACH: a photo-driven scroll sequence
 * ending at the closed station door, the application's real Login page,
 * an automatic door-opening cutscene, and the main-hall hub that routes
 * into the working application — all built on top of the app exactly as
 * it already runs (see src/App.jsx). Nothing in src/pages, src/services,
 * or the backend is touched by anything in this folder.
 *
 * `user` is the same session-restore-or-just-logged-in user object AppRoot
 * already tracks; `onLogin` is AppRoot's existing handleLogin, passed
 * straight through to the real Login page unchanged. `onEnterApp(route)`
 * hands control back to AppRoot once a hall option is chosen.
 */
export default function LandingExperience({ user, onLogin, onEnterApp }) {
  const stage = useGateStore((s) => s.stage)
  const setStage = useGateStore((s) => s.setStage)
  const [compact, setCompact] = useState(false)
  const prevUserRef = useRef(null)

  useScrollController(stage === 'sequence')
  useGateTransition()
  useDoorCutscene()

  // Fewer scroll steps on small screens — a shorter runway to the door.
  useEffect(() => {
    const check = () => setCompact(window.innerWidth < 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  // The moment the real sign-in succeeds (user flips null -> populated),
  // hide the login page and play the door-opening cutscene into the hall.
  useEffect(() => {
    if (!prevUserRef.current && user) setStage('cutscene')
    prevUserRef.current = user
  }, [user, setStage])

  // Once we leave the scroll sequence, pin the page at the top and stop
  // native scrolling — everything from here is click-driven.
  useEffect(() => {
    if (stage === 'sequence') {
      document.body.style.overflow = ''
      return
    }
    window.scrollTo(0, 0)
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
    }
  }, [stage])

  return (
    <div className="landing-root relative min-h-screen bg-navy-950">
      <Preloader />

      <div className="film-grain" />
      <div className="vignette" />

      <StationBackdrop />
      <ScrollOverlays />
      <EntryGate />
      <LoginReveal visible={stage === 'login'} onLogin={onLogin} />

      {stage === 'hub' && (
        <StationHub officerName={user?.full_name} onEnter={onEnterApp} />
      )}

      {/* Scroll spacer — drives scroll progress through scenes 1-4 only */}
      {stage === 'sequence' && (
        <div style={{ height: compact ? '420vh' : '600vh' }} className="relative z-0" />
      )}
    </div>
  )
}
