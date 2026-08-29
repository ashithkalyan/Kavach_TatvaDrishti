import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Shield } from 'lucide-react'
import { useGateStore } from '../store/gateStore'

const STATUSES = [
  'Loading case records…',
  'Initialising KAVACH AI…',
  'Preparing the district map…',
  'Establishing secure connection…',
]

const easeOut = [0.16, 1, 0.3, 1]

function getFontsReady() {
  return document.fonts?.ready ?? Promise.resolve()
}

export default function Preloader() {
  const [progress, setProgress] = useState(0)
  const [statusIndex, setStatusIndex] = useState(0)
  const [done, setDone] = useState(false)
  const setAssetsReady = useGateStore((s) => s.setAssetsReady)

  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const duration = 2000

    function tick(now) {
      const elapsed = now - start
      const pct = Math.min(1, elapsed / duration)
      setProgress(pct)
      setStatusIndex(Math.min(STATUSES.length - 1, Math.floor(pct * STATUSES.length)))
      if (pct < 1) {
        raf = requestAnimationFrame(tick)
      } else {
        getFontsReady().then(() => {
          setAssetsReady(true)
          setTimeout(() => setDone(true), 350)
        })
      }
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [setAssetsReady])

  return (
    <AnimatePresence>
      {!done && (
        <motion.div
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.7, ease: easeOut }}
          className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-navy-950"
        >
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="mb-9 flex flex-col items-center gap-3"
          >
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl"
              style={{ background: 'linear-gradient(135deg, #C5A028 0%, #8A6E1A 100%)', boxShadow: '0 8px 24px rgba(197,160,40,0.28)' }}
            >
              <Shield size={26} color="#fff" />
            </div>
            <div className="text-center">
              <div className="text-lg font-bold tracking-[0.08em] text-gold-500">KAVACH</div>
              <div className="mt-0.5 text-[0.65rem] uppercase tracking-[0.25em] text-white/40">
                Karnataka State Police
              </div>
            </div>
          </motion.div>

          <div className="w-64 sm:w-80">
            <div className="mb-2.5 flex items-center justify-between text-[0.68rem] uppercase tracking-[0.15em] text-white/40">
              <span>{STATUSES[statusIndex]}</span>
              <span className="text-gold-500">{Math.round(progress * 100)}%</span>
            </div>
            <div className="h-[3px] w-full overflow-hidden rounded-full bg-white/10">
              <motion.div className="h-full rounded-full" style={{ width: `${progress * 100}%`, background: 'linear-gradient(90deg, #A88420, #E8CC6A)' }} />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
