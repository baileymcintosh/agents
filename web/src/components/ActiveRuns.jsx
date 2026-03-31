import { useState, useEffect, useCallback } from 'react'
import { listRuns } from '../lib/github.js'
import RunStatus from './RunStatus.jsx'

function workflowLabel(name) {
  const n = (name || '').toLowerCase()
  if (n.includes('preliminary') || n.includes('prelim')) return { label: 'Prelim', color: 'bg-purple-100 text-purple-700' }
  if (n.includes('deep')) return { label: 'Deep', color: 'bg-blue-100 text-blue-700' }
  if (n.includes('session')) return { label: 'Session', color: 'bg-orange-100 text-orange-700' }
  return { label: name || 'Run', color: 'bg-gray-100 text-gray-700' }
}

function formatStarted(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function ActiveRuns() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastRefreshed, setLastRefreshed] = useState(null)

  const fetchRuns = useCallback(async () => {
    try {
      const data = await listRuns(40)
      const all = (data?.workflow_runs || [])
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      // Show in_progress, queued, and the most recent completed (last 10m)
      const cutoff = Date.now() - 10 * 60 * 1000
      const relevant = all.filter(r =>
        r.status === 'in_progress' ||
        r.status === 'queued' ||
        (r.status === 'completed' && new Date(r.updated_at).getTime() > cutoff)
      )
      setRuns(relevant)
      setLastRefreshed(new Date())
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load runs.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRuns()
    const id = setInterval(fetchRuns, 15000)
    return () => clearInterval(id)
  }, [fetchRuns])

  const activeOnly = runs.filter(r => r.status === 'in_progress' || r.status === 'queued')

  return (
    <div className="p-6 max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Active Runs</h1>
          {lastRefreshed && (
            <p className="text-xs text-gray-400 mt-0.5">
              Auto-refreshes every 15s · Last updated {lastRefreshed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </p>
          )}
        </div>
        <button
          onClick={() => { setLoading(true); fetchRuns() }}
          className="text-sm text-blue-600 hover:underline flex items-center gap-1"
        >
          {loading && (
            <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}

      {loading && runs.length === 0 && (
        <div className="flex items-center gap-2 text-sm text-gray-400 py-8 justify-center">
          <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading runs...
        </div>
      )}

      {!loading && activeOnly.length === 0 && (
        <div className="bg-white shadow-sm rounded-xl p-10 text-center text-sm text-gray-400">
          No active runs.
        </div>
      )}

      {activeOnly.length > 0 && (
        <div className="space-y-3">
          {activeOnly.map(run => {
            const wf = workflowLabel(run.name)
            return (
              <div key={run.id} className="bg-white shadow-sm rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${wf.color}`}>
                      {wf.label}
                    </span>
                    <span className="text-sm font-medium text-gray-900 truncate max-w-sm">
                      {run.display_title || run.name}
                    </span>
                  </div>
                  <span className="text-xs text-gray-400 flex-shrink-0">{formatStarted(run.run_started_at || run.created_at)}</span>
                </div>
                <RunStatus runId={run.id} />
              </div>
            )
          })}
        </div>
      )}

      {runs.length > activeOnly.length && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-gray-600 mb-3">Recently Completed</h2>
          <div className="space-y-2">
            {runs.filter(r => r.status === 'completed').map(run => {
              const wf = workflowLabel(run.name)
              return (
                <div key={run.id} className="bg-white shadow-sm rounded-xl px-5 py-3 flex items-center gap-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${wf.color}`}>
                    {wf.label}
                  </span>
                  <span className="text-sm text-gray-700 flex-1 truncate">{run.display_title || run.name}</span>
                  <span className={`text-xs font-medium ${run.conclusion === 'success' ? 'text-green-600' : 'text-red-500'}`}>
                    {run.conclusion || 'cancelled'}
                  </span>
                  <span className="text-xs text-gray-400">{formatStarted(run.updated_at)}</span>
                  <a href={run.html_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline flex-shrink-0">
                    Logs →
                  </a>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
