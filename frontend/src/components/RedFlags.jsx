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
      className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 h-full"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          Red Flags
        </h3>
        {sorted.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            {SEVERITY_ORDER.map((sev) =>
              countBySeverity[sev] > 0 ? (
                <span
                  key={sev}
                  className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${SEVERITY_CONFIG[sev].badge}`}
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
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center py-12 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center mb-4">
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
            <p className="text-emerald-400 font-semibold">No red flags detected</p>
            <p className="text-sm text-gray-500 mt-1">All checks passed successfully.</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Flags list */}
      <motion.ul
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-3"
      >
        {sorted.map((flag, i) => {
          const sev = normalizeSeverity(flag.severity)
          const cfg = SEVERITY_CONFIG[sev]
          return (
            <motion.li
              key={i}
              variants={itemVariants}
              className={`rounded-xl border p-4 ${cfg.rowBorder} ${cfg.rowBg}`}
            >
              <div className="flex items-start gap-3">
                {/* Left bar accent */}
                <div className={`w-1 self-stretch rounded-full flex-shrink-0 ${cfg.bar}`} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1.5">
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full border font-bold ${cfg.badge}`}
                    >
                      {cfg.label}
                    </span>
                    {flag.category && (
                      <span className="text-xs text-gray-500 font-medium bg-gray-800/60 px-2 py-0.5 rounded-full border border-gray-700/60">
                        {flag.category}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {flag.description || flag.message || flag.detail || String(flag)}
                  </p>
                  {flag.confidence !== undefined && (
                    <div className="mt-2 flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${cfg.bar}`}
                          style={{ width: `${Math.round(flag.confidence * 100)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-gray-500 font-mono">
                        {Math.round(flag.confidence * 100)}% confidence
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </motion.li>
          )
        })}
      </motion.ul>
    </motion.div>
  )
}
