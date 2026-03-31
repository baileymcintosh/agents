import { useState, useEffect } from 'react'
import { readRepoFile, listRuns, dispatchWorkflow } from '../lib/github.js'

function formatProjectName(repoName) {
  return repoName
    .split('-')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function formatDuration(run) {
  if (!run.run_started_at) return '—'
  const start = new Date(run.run_started_at)
  const end = run.status === 'completed' && run.updated_at ? new Date(run.updated_at) : new Date()
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function workflowLabel(name) {
  const n = (name || '').toLowerCase()
  if (n.includes('preliminary') || n.includes('prelim')) return { label: 'Prelim', color: 'bg-purple-100 text-purple-700' }
  if (n.includes('deep')) return { label: 'Deep', color: 'bg-blue-100 text-blue-700' }
  if (n.includes('session')) return { label: 'Session', color: 'bg-orange-100 text-orange-700' }
  return { label: name || 'Run', color: 'bg-gray-100 text-gray-700' }
}

function StatusBadge({ status, conclusion }) {
  if (status === 'completed') {
    if (conclusion === 'success') return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">Success</span>
    if (conclusion === 'failure') return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Failed</span>
    return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{conclusion || 'Cancelled'}</span>
  }
  if (status === 'in_progress' || status === 'queued') {
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
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{status || 'Unknown'}</span>
}

function ExternalLinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
  )
}

export default function ProjectDetail({ params, navigate, onToast }) {
  const repoName = params.repoName
  const [brief, setBrief] = useState(null)
  const [briefExpanded, setBriefExpanded] = useState(false)
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [reportExcerpt, setReportExcerpt] = useState(null)
  const [memory, setMemory] = useState(null)
  const [feedback, setFeedback] = useState('')
  const [iterating, setIterating] = useState(false)

  useEffect(() => {
    if (!repoName) return
    loadAll()
  }, [repoName])

  async function loadAll() {
    // Load brief, report excerpt, memory in parallel
    const [briefText, reportText, memoryText] = await Promise.all([
      readRepoFile(repoName, 'BRIEF.md'),
      readRepoFile(repoName, 'final_report.md'),
      readRepoFile(repoName, 'project_memory.json'),
    ])

    setBrief(briefText)
    if (reportText) {
      setReportExcerpt(reportText.slice(0, 400))
    }
    if (memoryText) {
      try {
        setMemory(JSON.parse(memoryText))
      } catch {
        // ignore parse errors
      }
    }

    // Load runs
    try {
      const data = await listRuns(40)
      const all = (data?.workflow_runs || []).sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      )
      setRuns(all)
    } catch {
      // runs are best-effort
    } finally {
      setRunsLoading(false)
    }
  }

  async function handleIterate(e) {
    e.preventDefault()
    setIterating(true)
    try {
      const inputs = {
        project_name: repoName,
        repo_name: repoName,
      }
      if (feedback.trim()) inputs.feedback = feedback.trim()
      await dispatchWorkflow('deep.yml', inputs)
      onToast('Deep run dispatched with feedback!')
      setFeedback('')
    } catch (err) {
      onToast(err.message || 'Failed to dispatch.', 'error')
    } finally {
      setIterating(false)
    }
  }

  const repoUrl = `https://github.com/baileymcintosh/${repoName}`
  const briefTruncated = brief && brief.length > 300 && !briefExpanded
  const displayBrief = briefTruncated ? brief.slice(0, 300) + '…' : brief

  return (
    <div className="p-6 max-w-7xl">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('library', {})}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-3 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Projects
        </button>

        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900">{formatProjectName(repoName)}</h1>
              <a
                href={repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
                title="Open on GitHub"
              >
                <ExternalLinkIcon />
              </a>
            </div>
            <p className="text-xs text-gray-400 font-mono mt-0.5">{repoName}</p>
          </div>
        </div>

        {brief && (
          <div className="mt-3 bg-gray-50 rounded-xl px-4 py-3">
            <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">{displayBrief}</p>
            {brief.length > 300 && (
              <button
                onClick={() => setBriefExpanded(e => !e)}
                className="text-xs text-blue-600 hover:underline mt-1"
              >
                {briefExpanded ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        )}
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left: Run timeline */}
        <div className="flex-1 min-w-0 space-y-4">
          <div className="bg-white shadow-sm rounded-xl">
            <div className="px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">Recent Runs</h2>
              <p className="text-xs text-gray-400 mt-0.5">All runs from the agents repo. Runs referencing this project appear at top.</p>
            </div>

            {runsLoading && (
              <div className="px-5 py-8 text-center text-sm text-gray-400 flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading runs...
              </div>
            )}

            {!runsLoading && runs.length === 0 && (
              <div className="px-5 py-8 text-center text-sm text-gray-400">No runs found.</div>
            )}

            {runs.length > 0 && (
              <div className="divide-y divide-gray-50">
                {runs.slice(0, 15).map(run => {
                  const wf = workflowLabel(run.name)
                  return (
                    <div key={run.id} className="px-5 py-3 flex items-center gap-3 flex-wrap hover:bg-gray-50 transition-colors">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium flex-shrink-0 ${wf.color}`}>
                        {wf.label}
                      </span>
                      <StatusBadge status={run.status} conclusion={run.conclusion} />
                      <span className="text-xs text-gray-500 flex-shrink-0">{formatDate(run.run_started_at || run.created_at)}</span>
                      <span className="text-xs text-gray-400 flex-shrink-0">{formatDuration(run)}</span>
                      <span className="text-xs text-gray-600 truncate flex-1 min-w-0" title={run.display_title || run.name}>
                        {run.display_title || run.name}
                      </span>
                      <a
                        href={run.html_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline flex-shrink-0"
                      >
                        Logs →
                      </a>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Latest Report card */}
          {reportExcerpt && (
            <div className="bg-white shadow-sm rounded-xl p-5">
              <h2 className="text-sm font-semibold text-gray-900 mb-3">Latest Report</h2>
              <p className="text-sm text-gray-600 leading-relaxed whitespace-pre-wrap">
                {reportExcerpt}{reportExcerpt.length >= 400 ? '…' : ''}
              </p>
              <div className="mt-4">
                <button
                  onClick={() => navigate('report', { repoName })}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                >
                  Read Full Report
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Project info */}
        <div className="lg:w-80 xl:w-96 space-y-4 flex-shrink-0">
          {/* Iterate */}
          <div className="bg-white shadow-sm rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Iterate</h2>
            <form onSubmit={handleIterate} className="space-y-3">
              <textarea
                rows={3}
                value={feedback}
                onChange={e => setFeedback(e.target.value)}
                placeholder="Feedback for next run: e.g. Go deeper on the sanctions angle..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              <button
                type="submit"
                disabled={iterating}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2"
              >
                {iterating && (
                  <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                )}
                Launch Deep Run
              </button>
            </form>
          </div>

          {/* Memory */}
          <div className="bg-white shadow-sm rounded-xl p-5">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Memory</h2>
            {!memory ? (
              <p className="text-xs text-gray-400">Memory will appear after the first completed run.</p>
            ) : (
              <div className="space-y-4">
                {memory.verified_findings && memory.verified_findings.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Key Findings</h3>
                    <ul className="space-y-1.5">
                      {memory.verified_findings.slice(0, 5).map((f, i) => (
                        <li key={i} className="text-xs text-gray-700 flex gap-1.5">
                          <span className="text-green-500 flex-shrink-0 mt-0.5">✓</span>
                          <span>{typeof f === 'string' ? f : f.finding || JSON.stringify(f)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {memory.high_priority_questions && memory.high_priority_questions.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Open Questions</h3>
                    <ul className="space-y-1.5">
                      {memory.high_priority_questions.slice(0, 3).map((q, i) => (
                        <li key={i} className="text-xs text-gray-700 flex gap-1.5">
                          <span className="text-yellow-500 flex-shrink-0 mt-0.5">?</span>
                          <span>{typeof q === 'string' ? q : q.question || JSON.stringify(q)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {memory.useful_sources && memory.useful_sources.length > 0 && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Top Sources</h3>
                    <ul className="space-y-1.5">
                      {memory.useful_sources.slice(0, 3).map((s, i) => {
                        const url = typeof s === 'string' ? s : s.url || null
                        const label = typeof s === 'string' ? s : s.title || s.url || JSON.stringify(s)
                        return (
                          <li key={i} className="text-xs">
                            {url ? (
                              <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate block">
                                {label}
                              </a>
                            ) : (
                              <span className="text-gray-700">{label}</span>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
