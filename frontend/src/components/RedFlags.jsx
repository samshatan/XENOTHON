import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const SEVERITY_ORDER = ['critical', 'high', 'medium', 'low']

const SEVERITY_CONFIG = {
  critical: {
    badge: 'bg-violet-500/15 border-violet-500/30 text-violet-300',
    dot: 'bg-violet-400',
    bar: 'bg-violet-500',
    label: 'Critical',
    icon: '🔴',
    rowBorder: 'border-violet-500/20',
    rowBg: 'bg-violet-500/5',
  },
  high: {
    badge: 'bg-red-500/15 border-red-500/30 text-red-300',
    dot: 'bg-red-400',
    bar: 'bg-red-500',
    label: 'High',
    icon: '🟠',
    rowBorder: 'border-red-500/20',
    rowBg: 'bg-red-500/5',
  },
  medium: {
    badge: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
    dot: 'bg-amber-400',
    bar: 'bg-amber-500',
    label: 'Medium',
    icon: '🟡',
    rowBorder: 'border-amber-500/20',
    rowBg: 'bg-amber-500/5',
  },
  low: {
    badge: 'bg-yellow-500/15 border-yellow-500/30 text-yellow-300',
    dot: 'bg-yellow-400',
    bar: 'bg-yellow-500',
    label: 'Low',
    icon: '🟢',
    rowBorder: 'border-yellow-500/20',
    rowBg: 'bg-yellow-500/5',
  },
}

function normalizeSeverity(sev) {
  const s = (sev || '').toLowerCase()
  if (SEVERITY_ORDER.includes(s)) return s
  return 'medium'
}

function sortFlags(flags) {
  return [...flags].sort((a, b) => {
    const ia = SEVERITY_ORDER.indexOf(normalizeSeverity(a.severity))
    const ib = SEVERITY_ORDER.indexOf(normalizeSeverity(b.severity))
    return ia - ib
  })
}

const containerVariants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
}

const itemVariants = {
  hidden: { opacity: 0, x: -16 },
  visible: { opacity: 1, x: 0, transition: { type: 'spring', stiffness: 200, damping: 20 } },
}

export default function RedFlags({ flags = [] }) {
  const sorted = sortFlags(flags)

  const countBySeverity = SEVERITY_ORDER.reduce((acc, sev) => {
    acc[sev] = sorted.filter((f) => normalizeSeverity(f.severity) === sev).length
    return acc
  }, {})

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15 }}
      className="sentinel-glass rounded-3xl p-8 h-full shadow-[0_0_50px_rgba(0,0,0,0.3)]"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-4 bg-violet-400 rounded-full shadow-[0_0_8px_rgba(188,0,255,0.8)]" />
          <h3 className="text-xs font-black text-white uppercase tracking-[0.3em]">
            Identified Risks
          </h3>
        </div>
        {sorted.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            {SEVERITY_ORDER.map((sev) =>
              countBySeverity[sev] > 0 ? (
                <span
                  key={sev}
                  className={`text-[9px] px-2 py-0.5 rounded-lg border font-black tracking-widest uppercase ${SEVERITY_CONFIG[sev].badge}`}
                >
                  {countBySeverity[sev]} {SEVERITY_CONFIG[sev].label}
                </span>
              ) : null
            )}
          </div>
        )}
      </div>

      {/* No flags state */}
      <AnimatePresence>
        {sorted.length === 0 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-16 text-center bg-emerald-500/[0.02] border border-emerald-500/10 rounded-2xl"
          >
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 sentinel-border flex items-center justify-center mb-6">
              <svg
                className="w-8 h-8 text-emerald-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <p className="text-emerald-400 font-black tracking-widest uppercase text-xs">No threats detected</p>
            <p className="text-[11px] text-gray-500 mt-2 font-medium">Document satisfies all Sentinel protocol checks.</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Flags list */}
      <motion.ul
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-4"
      >
        {sorted.map((flag, i) => {
          const sev = normalizeSeverity(flag.severity)
          const cfg = SEVERITY_CONFIG[sev]
          return (
            <motion.li
              key={i}
              variants={itemVariants}
              className={`rounded-2xl border p-5 transition-all duration-300 backdrop-blur-sm ${cfg.rowBorder} ${cfg.rowBg} hover:bg-white/[0.04]`}
            >
              <div className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap mb-3">
                    <span
                      className={`text-[9px] px-2 py-0.5 rounded-lg border font-black tracking-widest uppercase ${cfg.badge}`}
                    >
                      {cfg.label}
                    </span>
                    {flag.category && (
                      <span className="text-[9px] text-white/40 font-black tracking-widest uppercase bg-white/5 px-2 py-0.5 rounded-lg sentinel-border">
                        {flag.category}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-200 leading-relaxed font-medium">
                    {flag.description || flag.message || flag.detail || String(flag)}
                  </p>
                </div>
              </div>
            </motion.li>
          )
        })}
      </motion.ul>
    </motion.div>
  )
}
