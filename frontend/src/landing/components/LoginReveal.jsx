import { motion, AnimatePresence } from 'framer-motion'
import Login from '../../pages/Login'

const easeOut = [0.16, 1, 0.3, 1]

/**
 * Hosts the application's real, unmodified Login page (src/pages/Login.jsx)
 * as a full-screen reveal once the camera-push transition completes. Every
 * field, the register tab, the demo accounts, and the language toggle are
 * the exact same working component used everywhere else in KAVACH — only
 * its entrance is staged differently here.
 */
export default function LoginReveal({ visible, onLogin }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: easeOut }}
          className="fixed inset-0 z-[110]"
        >
          <Login onLogin={onLogin} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
