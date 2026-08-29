import { motion, AnimatePresence } from 'framer-motion'
import { Shield } from 'lucide-react'
import { useGateStore } from '../store/gateStore'

const easeOut = [0.16, 1, 0.3, 1]

export default function EntryGate() {
  const phase = useGateStore((s) => s.phase)
  const phaseProgress = useGateStore((s) => s.phaseProgress)
  const stage = useGateStore((s) => s.stage)
  const setStage = useGateStore((s) => s.setStage)

  const visible = stage === 'sequence' && phase === 'door' && phaseProgress > 0.85

  return (
    <div className="pointer-events-none fixed inset-0 z-20 flex items-end justify-center pb-[12vh] sm:pb-[14vh]">
      <AnimatePresence>
        {visible && (
          <motion.button
            initial={{ opacity: 0, y: 20, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.96 }}
            transition={{ duration: 0.7, ease: easeOut }}
            onClick={() => setStage('transitioning')}
            className="group pointer-events-auto flex items-center gap-3 rounded-lg border border-gold-500/40 bg-navy-950/75 px-7 py-3.5 backdrop-blur-md transition-colors hover:border-gold-500/80 hover:bg-navy-900/80"
          >
            <Shield size={16} className="text-gold-400" />
            <span className="text-xs font-semibold uppercase tracking-[0.22em] text-white/90 group-hover:text-white sm:text-sm">
              Officer Sign-In
            </span>
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
}
