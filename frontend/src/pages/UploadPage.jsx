import React, { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { uploadDocument } from '../api'

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/tiff': ['.tiff', '.tif'],
}

const MAX_SIZE = 10 * 1024 * 1024 // 10 MB

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileTypeIcon({ type }) {
  if (type === 'application/pdf') {
    return (
      <div className="w-12 h-12 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0">
        <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      </div>
    )
  }
  return (
    <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center flex-shrink-0">
      <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
      </svg>
    </div>
  )
}

const features = [
  { icon: '🔍', label: 'OCR Extraction', desc: 'Reads text from any document format' },
  { icon: '🧠', label: 'NER Analysis', desc: 'Identifies entities & validates data' },
  { icon: '🌐', label: 'Web Verification', desc: 'Cross-references with public records' },
  { icon: '👁️', label: 'Vision AI', desc: 'Detects visual tampering & forgery' },
  { icon: '📊', label: 'Trust Score', desc: 'Instant fraud probability score' },
]

export default function UploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)

  const onDrop = useCallback((accepted, rejected) => {
    setError(null)
    if (rejected.length > 0) {
      const err = rejected[0].errors[0]
      if (err.code === 'file-too-large') {
        setError('File is too large. Maximum size is 10 MB.')
      } else if (err.code === 'file-invalid-type') {
        setError('Unsupported file type. Please upload PDF, JPG, PNG, or TIFF.')
      } else {
        setError(err.message)
      }
      return
    }
    if (accepted.length > 0) {
      setFile(accepted[0])
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE,
    multiple: false,
  })

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    try {
      const data = await uploadDocument(file)
      navigate(`/result/${data.job_id}`)
    } catch (err) {
      const msg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Upload failed. Please try again.'
      setError(msg)
      setUploading(false)
    }
  }

  const removeFile = () => {
    setFile(null)
    setError(null)
  }

  const borderColor = isDragReject
    ? 'border-red-500 bg-red-500/5'
    : isDragActive
    ? 'border-blue-400 bg-blue-500/10'
    : file
    ? 'border-emerald-500/50 bg-emerald-500/5'
    : 'border-gray-700 hover:border-gray-500'

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col items-center justify-center px-4 py-12 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-2xl relative z-10">
        {/* Hero text */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-10"
        >
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 rounded-full px-4 py-1.5 mb-5">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            <span className="text-xs text-blue-300 font-semibold tracking-widest uppercase">
              AI-Powered Analysis
            </span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold mb-3 leading-tight">
            <span className="bg-gradient-to-r from-white via-blue-100 to-blue-300 bg-clip-text text-transparent">
              Detect Document
            </span>
            <br />
            <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
              Fraud Instantly
            </span>
          </h1>
          <p className="text-gray-400 text-lg max-w-md mx-auto">
            Upload any document and our multi-agent AI pipeline will verify its authenticity in seconds.
          </p>
        </motion.div>

        {/* Drop zone */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mb-4"
        >
          <div
            {...getRootProps()}
            className={`relative rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all duration-300 ${borderColor}`}
          >
            <input {...getInputProps()} />

            <AnimatePresence mode="wait">
              {file ? (
                <motion.div
                  key="file-preview"
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="flex items-center gap-4 bg-gray-800/60 rounded-xl p-4 text-left"
                  onClick={(e) => e.stopPropagation()}
                >
                  <FileTypeIcon type={file.type} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-100 truncate">{file.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {file.type || 'Unknown type'} · {formatBytes(file.size)}
                    </p>
                    <div className="flex items-center gap-1.5 mt-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <span className="text-xs text-emerald-400">Ready to analyze</span>
                    </div>
                  </div>
                  <button
                    onClick={removeFile}
                    className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors flex-shrink-0"
                    aria-label="Remove file"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </motion.div>
              ) : (
                <motion.div
                  key="drop-prompt"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                >
                  <motion.div
                    animate={{ y: isDragActive ? -6 : 0 }}
                    transition={{ type: 'spring', stiffness: 300 }}
                    className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-blue-500/20 flex items-center justify-center mx-auto mb-4"
                  >
                    <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                    </svg>
                  </motion.div>
                  {isDragActive && !isDragReject && (
                    <p className="text-blue-300 font-semibold text-lg mb-1">Drop it here!</p>
                  )}
                  {isDragReject && (
                    <p className="text-red-400 font-semibold text-lg mb-1">File type not supported</p>
                  )}
                  {!isDragActive && (
                    <>
                      <p className="text-gray-200 font-semibold text-lg mb-1">
                        Drag & drop your document here
                      </p>
                      <p className="text-gray-500 text-sm mb-4">or click to browse files</p>
                    </>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Supported formats */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap items-center justify-center gap-2 mb-6 text-xs text-gray-500"
        >
          <span>Supported formats:</span>
          {['PDF', 'JPG', 'JPEG', 'PNG', 'TIFF'].map((fmt) => (
            <span
              key={fmt}
              className="px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-400 font-mono"
            >
              {fmt}
            </span>
          ))}
          <span className="ml-1">· Max 10 MB</span>
        </motion.div>

        {/* Error message */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="mb-4 flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-sm text-red-300"
            >
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Upload button */}
        <motion.button
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          whileHover={file && !uploading ? { scale: 1.02 } : {}}
          whileTap={file && !uploading ? { scale: 0.98 } : {}}
          onClick={handleUpload}
          disabled={!file || uploading}
          className={`w-full py-4 rounded-2xl font-semibold text-base transition-all duration-300 relative overflow-hidden
            ${file && !uploading
              ? 'bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white shadow-lg shadow-blue-500/25 cursor-pointer'
              : 'bg-gray-800 text-gray-600 cursor-not-allowed'
            }`}
        >
          {uploading ? (
            <span className="flex items-center justify-center gap-3">
              <svg className="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Uploading & Analyzing…
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Analyze Document
            </span>
          )}
        </motion.button>

        {/* Features grid */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
          className="mt-12 grid grid-cols-2 sm:grid-cols-3 gap-3"
        >
          {features.map((f, i) => (
            <motion.div
              key={f.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 + i * 0.07 }}
              className="bg-gray-900/60 border border-gray-800/80 rounded-xl p-4 hover:border-gray-700 transition-colors"
            >
              <span className="text-2xl mb-2 block">{f.icon}</span>
              <p className="text-sm font-semibold text-gray-200">{f.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{f.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  )
}
