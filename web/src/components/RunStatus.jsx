import { useState, useEffect, useRef } from 'react'
import { getRun } from '../lib/github.js'

function getPhaseLabel(status, elapsedSeconds) {
  if (status === 'queued') return 'Waiting to start...'
  const mins = elapsedSeconds / 60
  if (mins < 3) return 'Setting up environment'
  if (mins < 8) return 'Running preliminary research'
  if (mins < 20) return 'Collaborative session in progress'
  if (mins < 45) return 'Verifying claims'
  return 'Generating final report'
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (mins < 60) return `${mins}m ${secs}s`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function StatusBadge({ status, conclusion }) {
  if (status === 'completed') {
    if (conclusion === 'success') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
          Success
        </span>
      )
    }
    if (conclusion === 'failure') {
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
          Failed
        </span>
      )
    }
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        {conclusion || 'Cancelled'}
      </span>
    )
  }
  if (status === 'in_progress') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Running
      </span>
    )
  }
  if (status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
        Queued
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      {status || 'Unknown'}
    </span>
  )
}

export default function RunStatus({ runId }) {
  const [run, setRun] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const pollRef = useRef(null)
  const tickRef = useRef(null)

  useEffect(() => {
    fetchRun()
    pollRef.current = setInterval(fetchRun, 10000)
    return () => {
      clearInterval(pollRef.current)
      clearInterval(tickRef.current)
    }
  }, [runId])

  async function fetchRun() {
    try {
      const data = await getRun(runId)
      setRun(data)
      // Update elapsed and start ticking if in progress
      if (data.run_started_at) {
        const startMs = new Date(data.run_started_at).getTime()
        const endMs = data.status === 'completed' && data.updated_at
          ? new Date(data.updated_at).getTime()
          : null
        if (endMs) {
          setElapsed(Math.floor((endMs - startMs) / 1000))
          clearInterval(tickRef.current)
        } else {
          setElapsed(Math.floor((Date.now() - startMs) / 1000))
          clearInterval(tickRef.current)
          tickRef.current = setInterval(() => {
            setElapsed(Math.floor((Date.now() - startMs) / 1000))
          }, 1000)
        }
      }
    } catch {
      // silently fail
    }
  }

  if (!run) {
    return (
      <div className="flex items-center gap-2 text-xs text-gray-400">
        <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading...
      </div>
    )
  }

  const phase = getPhaseLabel(run.status, elapsed)

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <StatusBadge status={run.status} conclusion={run.conclusion} />
      <span className="text-xs text-gray-500 font-mono">{formatElapsed(elapsed)}</span>
      <span className="text-xs text-gray-400 italic">{phase}</span>
      {run.html_url && (
        <a
          href={run.html_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:underline ml-auto"
        >
          View full logs →
        </a>
      )}
    </div>
  )
}
