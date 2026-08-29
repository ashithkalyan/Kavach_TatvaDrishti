import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGateStore } from '../store/gateStore'

const easeOut = [0.16, 1, 0.3, 1]
const easeInOut = [0.65, 0, 0.35, 1]

const PHASE_CONTENT = {
  establishing: {
    eyebrow: 'Karnataka State Police',
    lines: [
      { text: 'Every case', className: 'text-white' },
      { text: 'leaves a trace.', className: 'text-gold-400' },
      { text: 'KAVACH — AI Crime Intelligence Platform', small: true },
    ],
  },
  approach: {
    eyebrow: 'Built for the field',
    lines: [
      { text: 'Faster leads.', className: 'text-white' },
      { text: 'Clearer patterns.', className: 'text-white' },
      { text: 'Smarter cases.', className: 'text-gold-400' },
    ],
  },
  signage: {
    eyebrow: 'One platform',
    lines: [
      { text: 'Every division,', className: 'text-white' },
      { text: 'one station.', className: 'text-gold-400' },
    ],
  },
  door: { lines: [] },
}

function ScrollPrompt() {
  return (
    <motion.div
      className="flex flex-col items-center gap-3"
      animate={{ y: [0, -8, 0] }}
      transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
    >
      <span className="text-xs sm:text-sm uppercase tracking-[0.35em] text-gold-400">
        Scroll to Enter
      </span>
      <motion.div
        className="h-10 w-px bg-gradient-to-b from-gold-400 to-transparent"
        animate={{ opacity: [0.3, 1, 0.3] }}
        transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
      />
    </motion.div>
  )
}

export default function ScrollOverlays() {
  const stage = useGateStore((s) => s.stage)
  const phase = useGateStore((s) => s.phase)
  const phaseProgress = useGateStore((s) => s.phaseProgress)

  const content = PHASE_CONTENT[phase] ?? { lines: [] }

  const opacity = useMemo(() => {
    if (stage !== 'sequence') return 0
    if (phase === 'door') return phaseProgress >= 0.5 ? 1 : 0
    const p = phaseProgress
    const fadeIn = Math.min(1, p / 0.25)
    const fadeOut = Math.min(1, (1 - p) / 0.25)
    return Math.max(0, Math.min(fadeIn, fadeOut))
  }, [stage, phase, phaseProgress])

  if (stage !== 'sequence') return null

  return (
    <div className="pointer-events-none fixed inset-0 z-20 flex items-center justify-center">
      <AnimatePresence mode="wait">
        <motion.div
          key={phase}
          initial={{ opacity: 0 }}
          animate={{ opacity }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: easeInOut }}
          className="flex max-w-2xl flex-col items-center px-6 text-center"
        >
          {content.eyebrow && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: opacity * 0.85, y: 0 }}
              transition={{ duration: 0.5, ease: easeOut }}
              className="mb-5 flex items-center gap-2 text-[0.7rem] uppercase tracking-[0.3em] text-white/50 sm:text-xs"
            >
              <span className="h-1 w-1 rounded-full bg-gold-500" />
              {content.eyebrow}
            </motion.div>
          )}

          {phase === 'door' && phaseProgress >= 0.5 ? (
            <ScrollPrompt />
          ) : (
            <div className="flex flex-col gap-1 sm:gap-2">
              {content.lines.map((line, i) =>
                line.small ? (
                  <motion.p
                    key={i}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: opacity * 0.7, y: 0 }}
                    transition={{ duration: 0.6, ease: easeOut, delay: i * 0.12 }}
                    className="mt-5 text-xs uppercase tracking-[0.3em] text-white/50 sm:text-sm"
                  >
                    {line.text}
                  </motion.p>
                ) : (
                  <motion.h1
                    key={i}
                    initial={{ opacity: 0, y: 24 }}
                    animate={{ opacity, y: 0 }}
                    transition={{ duration: 0.7, ease: easeOut, delay: i * 0.12 }}
                    className={`font-semibold leading-[1.1] text-4xl sm:text-6xl md:text-7xl ${line.className ?? ''}`}
                  >
                    {line.text}
                  </motion.h1>
                )
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
