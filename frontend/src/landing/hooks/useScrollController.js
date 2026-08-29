import { useEffect, useRef } from 'react'
import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGateStore } from '../store/gateStore'

gsap.registerPlugin(ScrollTrigger)

/**
 * Sets up Lenis smooth scroll + a single GSAP ScrollTrigger that scrubs
 * scrollProgress (0..1) into the gate store across the full page height.
 * When scroll is locked (during the sign-in transition), Lenis is stopped
 * so no further scroll input is processed.
 */
export function useScrollController(enabled) {
  const setScrollProgress = useGateStore((s) => s.setScrollProgress)
  const scrollLocked = useGateStore((s) => s.scrollLocked)
  const lenisRef = useRef(null)

  useEffect(() => {
    if (!enabled) return

    const lenis = new Lenis({ duration: 1.1, smoothWheel: true, lerp: 0.1 })
    lenisRef.current = lenis

    let rafId = 0
    function raf(time) {
      lenis.raf(time)
      ScrollTrigger.update()
      rafId = requestAnimationFrame(raf)
    }
    rafId = requestAnimationFrame(raf)

    const st = ScrollTrigger.create({
      start: 0,
      end: () => document.documentElement.scrollHeight - window.innerHeight,
      onUpdate: (self) => setScrollProgress(self.progress),
    })

    return () => {
      cancelAnimationFrame(rafId)
      lenis.destroy()
      lenisRef.current = null
      st.kill()
    }
  }, [enabled, setScrollProgress])

  useEffect(() => {
    const lenis = lenisRef.current
    if (!lenis) return
    if (scrollLocked) lenis.stop()
    else lenis.start()
  }, [scrollLocked])
}
