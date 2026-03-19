import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { CircularProgressbar, buildStyles } from 'react-circular-progressbar'
import 'react-circular-progressbar/dist/styles.css'

function getScoreConfig(score) {
  if (score >= 75) {
    return {
      label: 'AUTHENTIC',
      icon: '✓',
      color: '#10b981',
      trailColor: '#10b98130',
      badgeBg: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
      glowColor: 'shadow-emerald-500/20',
      desc: 'This document appears legitimate. No significant fraud indicators were detected.',
    }
  }
  if (score >= 40) {
    return {
      label: 'SUSPICIOUS',
      icon: '⚠',
      color: '#f59e0b',
      trailColor: '#f59e0b30',
      badgeBg: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
      glowColor: 'shadow-amber-500/20',
      desc: 'Some anomalies were detected. Manual review is recommended before trusting this document.',
    }
  }
  return {
    label: 'FRAUDULENT',
    icon: '✗',
    color: '#ef4444',
    trailColor: '#ef444430',
    badgeBg: 'bg-red-500/15 border-red-500/30 text-red-300',
    glowColor: 'shadow-red-500/20',
    desc: 'High probability of fraud detected. This document should not be trusted.',
  }
}

function useCountUp(target, duration = 1400) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    let start = null
    const step = (timestamp) => {
      if (!start) start = timestamp
      const elapsed = timestamp - start
      const progress = Math.min(elapsed / duration, 1)
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(eased * target))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target, duration])
  return value
}

export default function TrustScore({ score = 0, verdict, summary }) {
  const cfg = getScoreConfig(score)
  const displayScore = useCountUp(score)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="sentinel-glass rounded-3xl p-8 flex flex-col items-center text-center h-full shadow-[0_0_50px_rgba(0,0,0,0.4)]"
    >
      <div className="flex items-center gap-2 mb-8 self-start">
        <div className="w-1.5 h-4 bg-cyan-400 rounded-full shadow-[0_0_8px_rgba(34,211,238,0.8)]" />
        <h3 className="text-xs font-black text-white uppercase tracking-[0.3em]">
          Audit Verdict
        </h3>
      </div>

      {/* Circular gauge */}
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.1, type: 'spring', damping: 15 }}
        className={`w-52 h-52 mb-8 relative group`}
      >
        <div className={`absolute inset-0 rounded-full blur-3xl opacity-20 transition-all duration-700 ${cfg.glowColor}`} />
        <CircularProgressbar
          value={displayScore}
          maxValue={100}
          text={`${displayScore}`}
          styles={buildStyles({
            rotation: 0,
            strokeLinecap: 'butt',
            textSize: '24px',
            pathTransitionDuration: 1.5,
            pathColor: cfg.color,
            textColor: '#fff',
            trailColor: 'rgba(255,255,255,0.05)',
          })}
        />
        <div className="absolute inset-0 border-[10px] border-white/5 rounded-full pointer-events-none" />
        <div className="absolute -bottom-2 translate-y-1/2 left-1/2 -translate-x-1/2 px-3 py-1 bg-gray-900 border border-white/10 rounded-lg shadow-2xl">
          <span className="text-[10px] font-black tracking-widest text-cyan-500/80">SENTINEL-X</span>
        </div>
      </motion.div>

      {/* Verdict badge */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className={`flex items-center gap-2 px-6 py-2.5 rounded-2xl border-2 font-black text-xs tracking-[0.15em] mb-6 shadow-xl ${cfg.badgeBg}`}
      >
        <span className="text-base">{cfg.icon}</span>
        {verdict || cfg.label}
      </motion.div>

      {/* Summary text */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        className="text-sm text-gray-400 leading-relaxed font-medium px-4"
      >
        {summary || cfg.desc}
      </motion.p>

      {/* Score bar legend */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.65 }}
        className="mt-auto pt-10 w-full"
      >
        <div className="flex justify-between text-[9px] text-gray-600 font-black uppercase tracking-widest mb-2 px-1">
          <span>High Risk</span>
          <span>Validated</span>
        </div>
        <div className="flex rounded-full overflow-hidden h-1 sentinel-border">
          <div className="flex-1 bg-red-500/40" />
          <div className="flex-1 bg-amber-500/40" />
          <div className="flex-1 bg-emerald-500/40" />
        </div>
      </motion.div>
    </motion.div>
  )
}
