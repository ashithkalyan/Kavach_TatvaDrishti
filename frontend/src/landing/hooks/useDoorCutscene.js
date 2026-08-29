import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { useGateStore } from '../store/gateStore'

/**
 * When stage flips to 'cutscene' (right after a successful sign-in), this
 * plays a short automatic timeline that pushes the camera through the
 * now-open door (scene 4 -> 5) and on into the hall (scene 5 -> 6), then
 * hands off to the 'hub' stage where the six station rooms appear.
 *
 * This is intentionally NOT scroll-driven — once the officer is inside,
 * navigation becomes click-based rather than scroll-based.
 */
export function useDoorCutscene() {
  const stage = useGateStore((s) => s.stage)
  const setStage = useGateStore((s) => s.setStage)
  const setCutsceneT = useGateStore((s) => s.setCutsceneT)
  const tlRef = useRef(null)

  useEffect(() => {
    if (stage !== 'cutscene') return

    const obj = { t: 0 }
    const tl = gsap.timeline({ onComplete: () => setStage('hub') })
    tlRef.current = tl

    tl.to(obj, {
      t: 1,
      duration: 2.6,
      ease: 'power2.inOut',
      onUpdate: () => setCutsceneT(obj.t),
    })

    return () => {
      tl.kill()
      tlRef.current = null
    }
  }, [stage, setStage, setCutsceneT])
}
