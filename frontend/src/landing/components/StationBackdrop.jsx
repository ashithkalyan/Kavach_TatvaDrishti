import { useMemo } from 'react'
import { useGateStore } from '../store/gateStore'
import { STATION_SCENES, GATE_PROGRESS, HUB_PROGRESS } from '../data/stationScenes'

const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2)
const clamp01 = (n) => Math.min(1, Math.max(0, n))

/**
 * Renders the six station photographs as a single continuous "camera
 * flythrough": a slow, unbroken dolly-in zoom with crossfades between
 * consecutive photos as sceneProgress advances. Scenes 1-4 are
 * scroll-driven; scenes 4->5->6 auto-play once sign-in succeeds (see
 * useDoorCutscene). This component owns no interaction — it just paints
 * whatever sceneProgress currently is.
 */
export default function StationBackdrop() {
  const scrollProgress = useGateStore((s) => s.scrollProgress)
  const stage = useGateStore((s) => s.stage)
  const cutsceneT = useGateStore((s) => s.cutsceneT)
  const transitionT = useGateStore((s) => s.transitionT)

  const sceneProgress = useMemo(() => {
    if (stage === 'cutscene') {
      return GATE_PROGRESS + ease(cutsceneT) * (HUB_PROGRESS - GATE_PROGRESS)
    }
    if (stage === 'hub') return HUB_PROGRESS
    return clamp01(scrollProgress) * GATE_PROGRESS
  }, [stage, scrollProgress, cutsceneT])

  const { current, next, localT } = useMemo(() => {
    const kfs = STATION_SCENES.map((s) => s.keyframe)
    let i = 0
    for (; i < kfs.length - 1; i++) {
      if (sceneProgress >= kfs[i] && sceneProgress <= kfs[i + 1]) break
    }
    if (i >= kfs.length - 1) i = kfs.length - 2
    const span = kfs[i + 1] - kfs[i] || 1
    const t = clamp01((sceneProgress - kfs[i]) / span)
    return { current: STATION_SCENES[i], next: STATION_SCENES[i + 1], localT: t }
  }, [sceneProgress])

  // One continuous slow dolly-in across the whole journey, with a small
  // extra push while the door swings open during the cutscene.
  const cutsceneBoost = stage === 'cutscene' ? 0.07 * ease(cutsceneT) : stage === 'hub' ? 0.07 : 0
  const scale = 1 + 0.1 * sceneProgress + cutsceneBoost

  // Cool exterior -> warm interior grade crossfade, centred on the door
  // threshold (scene 4 closed -> scene 5 open).
  const warmT = useMemo(() => {
    const start = 0.58
    const end = 0.84
    if (sceneProgress <= start) return 0
    if (sceneProgress >= end) return 1
    return ease((sceneProgress - start) / (end - start))
  }, [sceneProgress])

  // Brief warm light-bleed as the door swings open, early in the cutscene.
  const flash = stage === 'cutscene' ? Math.max(0, Math.sin(Math.min(cutsceneT, 0.45) / 0.45 * Math.PI)) * 0.28 : 0

  // Push-in darken while the pre-login transition plays, just before the
  // real sign-in page appears.
  const gateDarken = stage === 'transitioning' ? ease(clamp01(transitionT)) * 0.7 : 0

  return (
    <div className="fixed inset-0 z-0 overflow-hidden bg-navy-950">
      <div className="absolute inset-0" style={{ transform: `scale(${scale})`, transformOrigin: '50% 42%' }}>
        <img
          src={current.src}
          alt={current.alt}
          className="absolute inset-0 h-full w-full object-cover"
          style={{ objectPosition: current.objectPosition }}
        />
        {next && localT > 0 && (
          <img
            src={next.src}
            alt={next.alt}
            className="absolute inset-0 h-full w-full object-cover"
            style={{ objectPosition: next.objectPosition, opacity: localT }}
          />
        )}
      </div>

      {/* Cool exterior grade */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'linear-gradient(180deg, rgba(5,16,31,0.38) 0%, rgba(5,16,31,0.68) 100%)',
          mixBlendMode: 'multiply',
          opacity: 1 - warmT,
        }}
      />
      {/* Warm interior grade */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: 'linear-gradient(180deg, rgba(30,22,10,0.3) 0%, rgba(11,29,58,0.58) 100%)',
          mixBlendMode: 'multiply',
          opacity: warmT,
        }}
      />
      {/* Brand accent tint, used sparingly */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: 'radial-gradient(ellipse at 50% 30%, rgba(197,160,40,0.05), transparent 62%)' }}
      />

      {flash > 0 && (
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: 'radial-gradient(circle at 50% 46%, rgba(255,224,168,0.9), transparent 55%)',
            opacity: flash,
          }}
        />
      )}

      {gateDarken > 0 && (
        <div className="pointer-events-none absolute inset-0 bg-black" style={{ opacity: gateDarken }} />
      )}
    </div>
  )
}
