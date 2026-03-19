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
      className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6 flex flex-col items-center text-center h-full"
    >
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-6">
        Trust Score
      </h3>

      {/* Circular gauge */}
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1, type: 'spring', stiffness: 120 }}
        className={`w-44 h-44 mb-6 drop-shadow-2xl ${cfg.glowColor}`}
      >
        <CircularProgressbar
          value={displayScore}
          maxValue={100}
          text={`${displayScore}`}
          styles={buildStyles({
            rotation: 0.75,
            strokeLinecap: 'round',
            textSize: '22px',
            pathTransitionDuration: 1.2,
            pathColor: cfg.color,
            textColor: cfg.color,
            trailColor: cfg.trailColor,
          })}
        />
      </motion.div>

      {/* Verdict badge */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className={`flex items-center gap-2 px-5 py-2 rounded-full border font-bold text-sm mb-4 ${cfg.badgeBg}`}
      >
        <span className="text-base">{cfg.icon}</span>
        {verdict || cfg.label}
      </motion.div>

      {/* Summary text */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.55 }}
        className="text-sm text-gray-400 leading-relaxed"
      >
        {summary || cfg.desc}
      </motion.p>

      {/* Score bar legend */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.65 }}
        className="mt-6 w-full"
      >
        <div className="flex rounded-full overflow-hidden h-2 mb-2">
          <div className="flex-1 bg-red-500/60" />
          <div className="flex-1 bg-amber-500/60" />
          <div className="flex-1 bg-emerald-500/60" />
        </div>
        <div className="flex justify-between text-[10px] text-gray-600 font-medium px-0.5">
          <span>0 – Fraud</span>
          <span>40 – Suspicious</span>
          <span>75 – Authentic</span>
        </div>
      </motion.div>
    </motion.div>
  )
}
