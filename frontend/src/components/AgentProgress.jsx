import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const AGENT_META = {
  ocr:     { label: 'OCR Engine',     icon: '📄', description: 'Text extraction' },
  ner:     { label: 'NER Analyzer',   icon: '🏷️', description: 'Entity recognition' },
  web:     { label: 'Web Checker',    icon: '🌐', description: 'Record verification' },
  anomaly: { label: 'Anomaly Scorer', icon: '📊', description: 'Fraud scoring' },
  vision:  { label: 'Vision AI',      icon: '👁️', description: 'Visual analysis' },
}

const STATUS_CONFIG = {
  pending: {
    badge: 'bg-gray-800 text-gray-500 border-gray-700',
    dot: 'bg-gray-600',
    label: 'Pending',
    ring: 'border-gray-800',
  },
  running: {
    badge: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    dot: 'bg-blue-400 animate-pulse',
    label: 'Running',
    ring: 'border-blue-500/40',
  },
  done: {
    badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: 'bg-emerald-400',
    label: 'Done',
    ring: 'border-emerald-500/30',
  },
  error: {
    badge: 'bg-red-500/15 text-red-300 border-red-500/30',
    dot: 'bg-red-400',
    label: 'Error',
    ring: 'border-red-500/30',
  },
}

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin text-blue-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function AgentRow({ agentKey, agent, compact }) {
  const meta = AGENT_META[agentKey] || { label: agentKey, icon: '🔧', description: '' }
  const cfg = STATUS_CONFIG[agent.status] || STATUS_CONFIG.pending

  if (compact) {
    return (
      <motion.div
        layout
        className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${cfg.ring} bg-gray-800/40`}
      >
        <span className="text-xl">{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200">{meta.label}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${cfg.badge}`}>
          {cfg.label}
        </span>
      </motion.div>
    )
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      className={`flex items-center gap-4 rounded-xl border px-5 py-4 transition-all duration-300 ${cfg.ring} ${
        agent.status === 'running' ? 'bg-blue-500/5' : 'bg-gray-800/30'
      }`}
    >
      {/* Icon */}
      <div className="relative flex-shrink-0">
        <div className="w-11 h-11 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center text-xl">
          {meta.icon}
        </div>
        {agent.status === 'running' && (
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-blue-500" />
          </span>
        )}
        {agent.status === 'done' && (
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5 bg-emerald-500 rounded-full items-center justify-center">
            <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </svg>
          </span>
        )}
        {agent.status === 'error' && (
          <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5 bg-red-500 rounded-full items-center justify-center">
            <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-semibold text-gray-100">{meta.label}</p>
          <span className="text-xs text-gray-600">{meta.description}</span>
        </div>
        <p className="text-xs text-gray-400 mt-0.5 truncate">{agent.message}</p>
      </div>

      {/* Status badge */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {agent.status === 'running' && <Spinner />}
        <span className={`text-xs px-2.5 py-1 rounded-full border font-semibold ${cfg.badge}`}>
          {cfg.label}
        </span>
      </div>
    </motion.div>
  )
}

export default function AgentProgress({ agents, compact = false }) {
  const agentKeys = Object.keys(AGENT_META)
  const doneCount = agentKeys.filter((k) => agents[k]?.status === 'done').length
  const progress = Math.round((doneCount / agentKeys.length) * 100)

  return (
    <div className={compact ? '' : 'bg-gray-900/60 border border-gray-800 rounded-2xl p-6'}>
      {!compact && (
        <>
          <div className="flex items-center justify-between mb-5">
            <h3 className="text-base font-bold text-gray-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              Agent Pipeline
            </h3>
            <span className="text-sm text-gray-400 font-medium">
              {doneCount} / {agentKeys.length} complete
            </span>
          </div>

          {/* Progress bar */}
          <div className="mb-5">
            <div className="flex justify-between text-xs text-gray-500 mb-1.5">
              <span>Overall progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-blue-500 to-violet-500 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>
          </div>
        </>
      )}

      <div className={compact ? 'grid grid-cols-2 sm:grid-cols-3 gap-3' : 'space-y-3'}>
        <AnimatePresence>
          {agentKeys.map((key, i) => (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
            >
              <AgentRow
                agentKey={key}
                agent={agents[key] || { status: 'pending', message: 'Waiting…' }}
                compact={compact}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
