import { motion } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, Network, BarChart2,
  FolderOpen, Users, Shield, ArrowRight,
} from 'lucide-react'
import { HUB_OPTIONS } from '../data/stationScenes'
import { useLanguage } from '../../i18n/LanguageContext'

const ICONS = { LayoutDashboard, MessageSquare, Network, BarChart2, FolderOpen, Users }
const easeOut = [0.16, 1, 0.3, 1]

export default function StationHub({ officerName, onEnter }) {
  const { t } = useLanguage()
  const central = HUB_OPTIONS.find((o) => o.central)
  const rooms = HUB_OPTIONS.filter((o) => !o.central)

  return (
    <div className="fixed inset-0 z-20 overflow-y-auto">
      {/* Legibility scrim over the hall photo */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-navy-950/80 via-navy-950/55 to-navy-950/90" />

      <div className="relative z-10 mx-auto flex min-h-full max-w-[900px] flex-col items-center px-5 py-14 sm:py-16">
        {/* Officer chip */}
        {officerName && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: easeOut, delay: 0.1 }}
            className="mb-6 flex items-center gap-2 self-end rounded-md border border-gold-500/25 bg-navy-950/60 px-3 py-1.5 backdrop-blur-md"
          >
            <Shield size={12} className="text-gold-400" />
            <span className="text-[0.65rem] font-medium uppercase tracking-[0.18em] text-white/75">
              {officerName}
            </span>
          </motion.div>
        )}

        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: easeOut, delay: 0.15 }}
          className="mb-10 text-center"
        >
          <p className="mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.3em] text-gold-500">
            Main Hall
          </p>
          <h1 className="text-2xl font-bold text-white sm:text-[1.75rem]">
            Where would you like to go?
          </h1>
          <p className="mt-2 text-sm text-white/50">
            Choose the dashboard, or step into a room to open that workspace.
          </p>
        </motion.div>

        {/* Dashboard — the central hall, primary destination */}
        {central && (
          <motion.button
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: easeOut, delay: 0.25 }}
            onClick={() => onEnter(central.route)}
            className="group mb-5 flex w-full items-center gap-5 rounded-xl border border-gold-500/30 bg-white/[0.04] p-5 text-left backdrop-blur-md transition-colors hover:border-gold-500/60 hover:bg-white/[0.06] sm:p-6"
          >
            <div
              className="flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-lg"
              style={{ background: 'linear-gradient(135deg, #C5A028 0%, #8A6E1A 100%)', boxShadow: '0 6px 18px rgba(197,160,40,0.25)' }}
            >
              <LayoutDashboard size={24} color="#fff" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-gold-500">
                {central.eyebrow}
              </div>
              <div className="mt-1 text-lg font-semibold text-white">{t(central.labelKey)}</div>
              <p className="mt-0.5 text-sm text-white/55">{central.description}</p>
            </div>
            <ArrowRight size={18} className="flex-shrink-0 text-white/30 transition-all group-hover:translate-x-1 group-hover:text-gold-400" />
          </motion.button>
        )}

        {/* The five rooms */}
        <div className="grid w-full auto-rows-fr grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {rooms.map((room, i) => {
            const Icon = ICONS[room.icon]
            return (
              <motion.button
                key={room.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: easeOut, delay: 0.35 + i * 0.06 }}
                onClick={() => onEnter(room.route)}
                className="group flex flex-col rounded-xl border border-white/10 bg-white/[0.03] p-4 text-left backdrop-blur-md transition-colors hover:border-gold-500/45 hover:bg-white/[0.06] sm:p-5"
              >
                <div className="mb-3 flex items-center justify-between">
                  <div className="flex h-9 w-9 items-center justify-center rounded-md bg-gold-500/12">
                    <Icon size={16} className="text-gold-400" />
                  </div>
                  <ArrowRight size={14} className="text-white/25 transition-all group-hover:translate-x-1 group-hover:text-gold-400" />
                </div>
                <div className="text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-white/40">
                  {room.eyebrow}
                </div>
                <div className="mt-1 text-[0.95rem] font-semibold text-white">{t(room.labelKey)}</div>
                <p className="mt-1 text-[0.78rem] leading-snug text-white/50">{room.description}</p>
              </motion.button>
            )
          })}
        </div>

        {/* Orientation footnote */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.75 }}
          className="mt-9 text-center text-xs text-white/35"
        >
          You can switch rooms anytime from the sidebar once inside.
        </motion.p>
      </div>
    </div>
  )
}
