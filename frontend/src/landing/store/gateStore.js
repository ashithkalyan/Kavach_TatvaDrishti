import { create } from 'zustand'

/**
 * Four scroll-driven phases, each corresponding to one of the first four
 * station photographs (aerial -> facade -> signage -> closed door).
 * Scenes 5-6 (door opening, interior hall) are not scroll-driven — they
 * play as an automatic cutscene once sign-in succeeds.
 */
export const PHASES = [
  { id: 'establishing', label: 'Approaching the station', start: 0.0, end: 0.25 },
  { id: 'approach', label: 'Nearing the entrance', start: 0.25, end: 0.5 },
  { id: 'signage', label: 'At the station house', start: 0.5, end: 0.75 },
  { id: 'door', label: 'Front door', start: 0.75, end: 1.0 },
]

function computePhase(p) {
  for (const ph of PHASES) {
    if (p >= ph.start && p <= ph.end) {
      const span = ph.end - ph.start || 1
      return { phase: ph.id, phaseProgress: (p - ph.start) / span }
    }
  }
  if (p < PHASES[0].start) return { phase: 'establishing', phaseProgress: 0 }
  return { phase: 'door', phaseProgress: 1 }
}

/**
 * stage moves forward through one path and is reset to 'sequence' on
 * sign-out (see LandingExperience.jsx):
 *   sequence -> transitioning -> login -> cutscene -> hub
 */
export const useGateStore = create((set, get) => ({
  scrollProgress: 0,
  phase: 'establishing',
  phaseProgress: 0,
  setScrollProgress: (p) => {
    const { phase, phaseProgress } = computePhase(p)
    set({ scrollProgress: p, phase, phaseProgress })
  },

  assetsReady: false,
  setAssetsReady: (v) => set({ assetsReady: v }),

  stage: 'sequence',
  setStage: (s) => set({ stage: s }),

  /** 0..1 progress of the pre-login camera push-in / fade to black */
  transitionT: 0,
  setTransitionT: (t) => set({ transitionT: t }),

  /** 0..1 progress of the post-login door-open -> hall-arrival cutscene */
  cutsceneT: 0,
  setCutsceneT: (t) => set({ cutsceneT: t }),

  scrollLocked: false,
  setScrollLocked: (v) => set({ scrollLocked: v }),

  /** Full reset used when the officer signs out, so a later sign-in
   *  replays the entry sequence from the beginning rather than resuming
   *  mid-hub. */
  reset: () => {
    const st = get()
    st.setScrollProgress(0)
    set({
      stage: 'sequence',
      transitionT: 0,
      cutsceneT: 0,
      scrollLocked: false,
    })
  },
}))
