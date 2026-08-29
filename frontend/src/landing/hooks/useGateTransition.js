import { useEffect, useRef } from 'react'
import gsap from 'gsap'
import { useGateStore } from '../store/gateStore'

/**
 * Drives the pre-login transition: a camera push-in and fade to black
 * (~1.1s) that plays after the officer taps "Officer Sign-In" at the door,
 * then hands off to the 'login' stage where the real Login page appears.
 */
export function useGateTransition() {
  const stage = useGateStore((s) => s.stage)
  const setStage = useGateStore((s) => s.setStage)
  const setTransitionT = useGateStore((s) => s.setTransitionT)
  const setScrollLocked = useGateStore((s) => s.setScrollLocked)
  const tlRef = useRef(null)

  useEffect(() => {
    if (stage !== 'transitioning') return

    const tl = gsap.timeline({
      defaults: { ease: 'power3.out' },
      onComplete: () => setStage('login'),
    })
    tlRef.current = tl
    setScrollLocked(true)

    tl.to(
      { t: 0 },
      {
        t: 1,
        duration: 1.1,
        onUpdate: function () {
          setTransitionT(this.targets()[0].t)
        },
      },
      0
    )

    return () => {
      tl.kill()
      tlRef.current = null
    }
  }, [stage, setStage, setTransitionT, setScrollLocked])
}
