import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const AGENT_META = {
  ocr:     { label: 'Reading Document',      icon: '🔐', description: 'OCR Scan' },
  ner:     { label: 'Extracting Entities',  icon: '🧬', description: 'Data Extraction' },
  web:     { label: 'Verifying Online',     icon: '🛰️', description: 'Global Registry' },
  anomaly: { label: 'Detecting Anomalies',   icon: '📡', description: 'Heuristic Audit' },
  vision:  { label: 'Visual Analysis',      icon: '👁️', description: 'Spectral Scan' },
}

const STATUS_CONFIG = {
  pending: {
    badge: 'bg-white/5 text-gray-500 border-white/10',
    dot: 'bg-gray-700',
    label: 'PENDING',
    ring: 'border-white/5',
  },
  running: {
    badge: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 shadow-[0_0_10px_rgba(6,182,212,0.15)]',
    dot: 'bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.8)]',
    label: 'ANALYZING',
    ring: 'border-cyan-500/40',
  },
  done: {
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    dot: 'bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]',
    label: 'VERIFIED',
    ring: 'border-emerald-500/30',
  },
  error: {
    badge: 'bg-red-500/10 text-red-400 border-red-500/30',
    dot: 'bg-red-400 shadow-[0_0_8px_rgba(239,68,68,0.8)]',
    label: 'FLAGGED',
    ring: 'border-red-500/30',
  },
}

function Spinner() {
  return (
    <div className="relative w-4 h-4">
      <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20" />
      <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-cyan-400 animate-spin" />
    </div>
  )
}

function AgentRow({ agentKey, agent, compact }) {
  const meta = AGENT_META[agentKey] || { label: agentKey, icon: '🔧', description: '' }
  const cfg = STATUS_CONFIG[agent.status] || STATUS_CONFIG.pending

  if (compact) {
    return (
      <motion.div
        layout
        className={`flex items-center gap-3 rounded-2xl sentinel-border px-4 py-3 bg-white/5 backdrop-blur-sm`}
      >
        <span className="text-lg opacity-80">{meta.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-bold text-gray-300 tracking-wide">{meta.label}</p>
        </div>
        <span className={`text-[9px] px-2 py-0.5 rounded-full border font-black tracking-tighter ${cfg.badge}`}>
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
      className={`flex items-center gap-4 rounded-2xl sentinel-border px-5 py-4 transition-all duration-500 backdrop-blur-md ${
        agent.status === 'running' ? 'bg-cyan-500/5 shadow-[0_0_30px_rgba(6,182,212,0.05)]' : 'bg-white/[0.02]'
      }`}
    >
      {/* Icon */}
      <div className="relative flex-shrink-0">
        <div className="w-12 h-12 rounded-2xl bg-gray-950/80 sentinel-border flex items-center justify-center text-2xl shadow-inner">
          {meta.icon}
        </div>
        {agent.status === 'running' && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-4 w-4 bg-cyan-500 border-2 border-gray-950" />
          </span>
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className={`text-sm font-black tracking-tight ${agent.status === 'running' ? 'text-cyan-100' : 'text-gray-100'}`}>
            {meta.label}
          </p>
          <span className="text-[10px] text-gray-600 font-mono hidden sm:inline">{meta.description}</span>
        </div>
        <p className="text-[11px] text-gray-500 mt-0.5 font-medium italic truncate">{agent.message}</p>
      </div>

      {/* Status */}
      <div className="flex items-center gap-3">
        {agent.status === 'running' && <Spinner />}
        <span className={`text-[10px] px-3 py-1 rounded-full border font-black tracking-widest ${cfg.badge}`}>
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
    <div className={compact ? '' : 'sentinel-glass rounded-3xl p-8 shadow-[0_0_50px_rgba(0,0,0,0.5)]'}>
      {!compact && (
        <>
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 sentinel-border flex items-center justify-center">
                <svg className="w-5 h-5 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-black text-white tracking-tight -mb-1">Sentinel Pipeline</h3>
                <span className="text-[10px] text-cyan-500/60 font-mono font-bold tracking-widest uppercase">Multi-Agent Verification</span>
              </div>
            </div>
            <div className="text-right">
              <span className="text-2xl font-black text-white">{progress}%</span>
              <p className="text-[10px] text-gray-500 font-bold uppercase tracking-tighter mt-1">{doneCount} / {agentKeys.length} PROTOCOLS</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mb-8 relative">
            <div className="h-1.5 bg-white/5 rounded-full overflow-hidden sentinel-border">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-400 via-blue-500 to-violet-500 rounded-full shadow-[0_0_15px_rgba(34,211,238,0.5)]"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.8, ease: 'circOut' }}
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
