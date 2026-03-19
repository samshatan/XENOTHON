import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import AgentProgress from '../components/AgentProgress'
import TrustScore from '../components/TrustScore'
import RedFlags from '../components/RedFlags'
import { createSSEConnection, getResult } from '../api'

const INITIAL_AGENTS = {
  ocr:     { name: 'OCR Engine',     status: 'pending', message: 'Waiting…' },
  ner:     { name: 'NER Analyzer',   status: 'pending', message: 'Waiting…' },
  web:     { name: 'Web Checker',    status: 'pending', message: 'Waiting…' },
  anomaly: { name: 'Anomaly Scorer', status: 'pending', message: 'Waiting…' },
  vision:  { name: 'Vision AI',      status: 'pending', message: 'Waiting…' },
}

export default function ResultPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [agents, setAgents] = useState(INITIAL_AGENTS)
  const [result, setResult] = useState(null)
  const [phase, setPhase] = useState('processing') // 'processing' | 'done' | 'error'
  const [errorMsg, setErrorMsg] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    // Try SSE stream first
    const es = createSSEConnection(
      jobId,
      (data) => {
        // Handle agent status updates
        if (data.type === 'agent_update' && data.agent) {
          setAgents((prev) => ({
            ...prev,
            [data.agent]: {
              ...prev[data.agent],
              status: data.status || prev[data.agent]?.status,
              message: data.message || prev[data.agent]?.message,
            },
          }))
        }

        // Handle full result payload
        if (data.type === 'result' || data.trust_score !== undefined) {
          setResult(data)
          setPhase('done')
          es.close()
        }

        // Handle errors
        if (data.type === 'error') {
          setErrorMsg(data.message || 'An error occurred during analysis.')
          setPhase('error')
          es.close()
        }
      },
      () => {
        // SSE error – fall back to polling the result endpoint
        es.close()
        pollResult()
      }
    )
    esRef.current = es

    return () => {
      es.close()
    }
  }, [jobId])

  const pollResult = async () => {
    let attempts = 0
    const MAX = 40
    const interval = setInterval(async () => {
      attempts++
      try {
        const data = await getResult(jobId)
        if (data && data.trust_score !== undefined) {
          setResult(data)
          setPhase('done')
          clearInterval(interval)
        }
      } catch {
        // keep trying
      }
      if (attempts >= MAX) {
        clearInterval(interval)
        setErrorMsg('Analysis timed out. Please try again.')
        setPhase('error')
      }
    }, 3000)
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] px-4 py-10 relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-violet-600/8 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-blue-600/8 rounded-full blur-3xl" />
      </div>

      <div className="max-w-5xl mx-auto relative z-10">
        {/* Page header */}
        <motion.div
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10 flex items-center justify-between flex-wrap gap-6"
        >
          <div>
            <h2 className="text-3xl font-black text-white tracking-tight">
              {phase === 'processing' ? (
                <span className="flex items-center gap-3">
                  <span className="text-neon-blue">Sentinel</span>
                  <span>Analysis In Progress</span>
                </span>
              ) : phase === 'done' ? (
                <span className="flex items-center gap-3">
                  <span className="text-emerald-400">Audit</span>
                  <span>Finalized</span>
                </span>
              ) : (
                <span className="text-red-400">Analysis Failed</span>
              )}
            </h2>
            <div className="flex items-center gap-3 mt-2">
              <span className="text-[10px] text-gray-500 font-mono tracking-widest uppercase bg-gray-900/50 px-2 py-0.5 rounded border border-gray-800">
                Job ID: {jobId}
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
            </div>
          </div>
          <motion.button
            whileHover={{ scale: 1.03, boxShadow: "0 0 20px rgba(6,182,212,0.1)" }}
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate('/')}
            className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-gray-900/80 hover:bg-gray-800/80 border border-white/10 text-gray-300 text-sm font-bold transition-all shadow-xl backdrop-blur-md"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
            </svg>
            New Audit
          </motion.button>
        </motion.div>

        {/* Error state */}
        <AnimatePresence>
          {phase === 'error' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-red-500/10 border border-red-500/30 rounded-2xl p-8 text-center"
            >
              <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-red-300 mb-2">Analysis Failed</h3>
              <p className="text-gray-400 mb-6">{errorMsg}</p>
              <button
                onClick={() => navigate('/')}
                className="px-6 py-3 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 text-red-300 font-semibold transition-colors"
              >
                Try Again
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Processing state */}
        {phase === 'processing' && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <AgentProgress agents={agents} />
          </motion.div>
        )}

        {/* Done state */}
        <AnimatePresence>
          {phase === 'done' && result && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-6"
            >
              {/* Trust Score + Red Flags side by side on large screens */}
              <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                <div className="lg:col-span-2">
                  <TrustScore
                    score={result.trust_score ?? result.score ?? 0}
                    verdict={result.verdict}
                    summary={result.summary}
                  />
                </div>
                <div className="lg:col-span-3">
                  <RedFlags flags={result.red_flags ?? result.flags ?? []} />
                </div>
              </div>

              {/* Agent summary card */}
              <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6"
              >
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                  Agent Pipeline Summary
                </h3>
                <AgentProgress agents={agents} compact />
              </motion.div>

              {/* Raw metadata if available */}
              {result.metadata && (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 }}
                  className="bg-gray-900/60 border border-gray-800 rounded-2xl p-6"
                >
                  <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                    Document Metadata
                  </h3>
                  <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    {Object.entries(result.metadata).map(([k, v]) => (
                      <div key={k} className="bg-gray-800/50 rounded-xl p-3">
                        <dt className="text-xs text-gray-500 capitalize">{k.replace(/_/g, ' ')}</dt>
                        <dd className="text-sm text-gray-200 font-medium mt-0.5 truncate">{String(v)}</dd>
                      </div>
                    ))}
                  </dl>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
