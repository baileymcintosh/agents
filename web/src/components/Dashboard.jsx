import { useState, useEffect, useCallback } from 'react'
import { listRuns, dispatchWorkflow } from '../lib/github.js'

const WORKFLOWS = [
  { file: 'prelim.yml', label: 'Prelim', color: 'bg-purple-100 text-purple-700' },
  { file: 'deep.yml', label: 'Deep', color: 'bg-blue-100 text-blue-700' },
  { file: 'research_session.yml', label: 'Session', color: 'bg-orange-100 text-orange-700' },
]

function workflowLabel(name) {
  const n = (name || '').toLowerCase()
  if (n.includes('preliminary') || n.includes('prelim')) return WORKFLOWS[0]
  if (n.includes('deep')) return WORKFLOWS[1]
  if (n.includes('session') || n.includes('research session')) return WORKFLOWS[2]
  return { file: '', label: name || 'Run', color: 'bg-gray-100 text-gray-700' }
}

function StatusBadge({ status, conclusion }) {
  if (status === 'completed') {
    if (conclusion === 'success') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
          Passed
        </span>
      )
    }
    if (conclusion === 'failure') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
          Failed
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
        Cancelled
      </span>
    )
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
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      {status || 'Unknown'}
    </span>
  )
}

function formatDuration(run) {
  if (!run.run_started_at) return '—'
  const start = new Date(run.run_started_at)
  const end = run.updated_at ? new Date(run.updated_at) : new Date()
  const secs = Math.floor((end - start) / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ${secs % 60}s`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

function formatStarted(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function Spinner({ className = 'h-4 w-4' }) {
  return (
    <svg className={`animate-spin ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

// ─── Launch Panel ───────────────────────────────────────────────────────────

function PrelimForm({ onDispatch }) {
  const [fields, setFields] = useState({
    project_name: '', brief: '', repo_name: '',
    prelim_quant_model: '', prelim_qual_model: '', prelim_reporter_model: '',
  })
  const [advanced, setAdvanced] = useState(false)

  function set(k, v) { setFields(f => ({ ...f, [k]: v })) }

  async function handleSubmit(e) {
    e.preventDefault()
    const inputs = { project_name: fields.project_name, brief: fields.brief }
    if (fields.repo_name.trim()) inputs.repo_name = fields.repo_name.trim()
    if (fields.prelim_quant_model.trim()) inputs.prelim_quant_model = fields.prelim_quant_model.trim()
    if (fields.prelim_qual_model.trim()) inputs.prelim_qual_model = fields.prelim_qual_model.trim()
    if (fields.prelim_reporter_model.trim()) inputs.prelim_reporter_model = fields.prelim_reporter_model.trim()
    await onDispatch('prelim.yml', inputs)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Project name <span className="text-red-500">*</span></label>
        <input
          type="text"
          required
          value={fields.project_name}
          onChange={e => set('project_name', e.target.value)}
          placeholder="iran-us-economy-2026"
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Brief <span className="text-red-500">*</span></label>
        <textarea
          required
          rows={4}
          value={fields.brief}
          onChange={e => set('brief', e.target.value)}
          placeholder="Analyze the economic relationship between Iran and the US through 2026..."
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Repo name <span className="text-gray-400 font-normal">(optional)</span></label>
        <input
          type="text"
          value={fields.repo_name}
          onChange={e => set('repo_name', e.target.value)}
          placeholder="Leave blank to auto-create"
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-400 mt-1">Leave blank to auto-create</p>
      </div>
      <div>
        <button
          type="button"
          onClick={() => setAdvanced(a => !a)}
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          <svg className={`h-3 w-3 transition-transform ${advanced ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Advanced
        </button>
        {advanced && (
          <div className="mt-3 space-y-3 pl-2 border-l-2 border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Quant model override</label>
              <input type="text" value={fields.prelim_quant_model} onChange={e => set('prelim_quant_model', e.target.value)} placeholder="e.g. claude-haiku-4-5-20251001" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Qual model override</label>
              <input type="text" value={fields.prelim_qual_model} onChange={e => set('prelim_qual_model', e.target.value)} placeholder="e.g. llama-3.3-70b-versatile" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Reporter model override</label>
              <input type="text" value={fields.prelim_reporter_model} onChange={e => set('prelim_reporter_model', e.target.value)} placeholder="e.g. llama-3.3-70b-versatile" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
        )}
      </div>
      <button type="submit" className="w-full bg-blue-600 text-white py-2 px-4 rounded text-sm font-medium hover:bg-blue-700 transition-colors">
        Launch Prelim Run
      </button>
    </form>
  )
}

function DeepForm({ onDispatch }) {
  const [fields, setFields] = useState({
    project_name: '', feedback: '', repo_name: '',
    deep_quant_model: '', deep_qual_model: '', deep_reporter_model: '',
  })
  const [advanced, setAdvanced] = useState(false)

  function set(k, v) { setFields(f => ({ ...f, [k]: v })) }

  async function handleSubmit(e) {
    e.preventDefault()
    const inputs = { project_name: fields.project_name }
    if (fields.feedback.trim()) inputs.feedback = fields.feedback.trim()
    if (fields.repo_name.trim()) inputs.repo_name = fields.repo_name.trim()
    if (fields.deep_quant_model.trim()) inputs.deep_quant_model = fields.deep_quant_model.trim()
    if (fields.deep_qual_model.trim()) inputs.deep_qual_model = fields.deep_qual_model.trim()
    if (fields.deep_reporter_model.trim()) inputs.deep_reporter_model = fields.deep_reporter_model.trim()
    await onDispatch('deep.yml', inputs)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Project name <span className="text-red-500">*</span></label>
        <input
          type="text"
          required
          value={fields.project_name}
          onChange={e => set('project_name', e.target.value)}
          placeholder="iran-us-economy-2026"
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Feedback <span className="text-gray-400 font-normal">(optional)</span></label>
        <textarea
          rows={4}
          value={fields.feedback}
          onChange={e => set('feedback', e.target.value)}
          placeholder="Incorporate this feedback from the prelim run..."
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Repo name <span className="text-gray-400 font-normal">(optional)</span></label>
        <input
          type="text"
          value={fields.repo_name}
          onChange={e => set('repo_name', e.target.value)}
          placeholder="Leave blank to auto-create"
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      <div>
        <button
          type="button"
          onClick={() => setAdvanced(a => !a)}
          className="text-xs text-blue-600 hover:underline flex items-center gap-1"
        >
          <svg className={`h-3 w-3 transition-transform ${advanced ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Advanced
        </button>
        {advanced && (
          <div className="mt-3 space-y-3 pl-2 border-l-2 border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Quant model override</label>
              <input type="text" value={fields.deep_quant_model} onChange={e => set('deep_quant_model', e.target.value)} placeholder="e.g. claude-haiku-4-5-20251001" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Qual model override</label>
              <input type="text" value={fields.deep_qual_model} onChange={e => set('deep_qual_model', e.target.value)} placeholder="e.g. gpt-4o-mini" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Reporter model override</label>
              <input type="text" value={fields.deep_reporter_model} onChange={e => set('deep_reporter_model', e.target.value)} placeholder="e.g. claude-sonnet-4-6" className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
        )}
      </div>
      <button type="submit" className="w-full bg-blue-600 text-white py-2 px-4 rounded text-sm font-medium hover:bg-blue-700 transition-colors">
        Launch Deep Run
      </button>
    </form>
  )
}

function SessionForm({ onDispatch }) {
  const [fields, setFields] = useState({
    time_budget: '2h',
    model_tier: 'sonnet',
    collab_turns: '3',
    dry_run: false,
  })

  function set(k, v) { setFields(f => ({ ...f, [k]: v })) }

  async function handleSubmit(e) {
    e.preventDefault()
    const inputs = {
      time_budget: fields.time_budget,
      model_tier: fields.model_tier,
      collab_turns: fields.collab_turns,
      dry_run: fields.dry_run ? 'true' : 'false',
    }
    await onDispatch('research_session.yml', inputs)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Time budget <span className="text-red-500">*</span></label>
        <input
          type="text"
          required
          value={fields.time_budget}
          onChange={e => set('time_budget', e.target.value)}
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-400 mt-1">e.g. 30m, 2h, 6h</p>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Model tier</label>
        <select
          value={fields.model_tier}
          onChange={e => set('model_tier', e.target.value)}
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="sonnet">sonnet (~$1-3 per 2h)</option>
          <option value="opus">opus (~$7-10 per 2h)</option>
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Collab turns</label>
        <select
          value={fields.collab_turns}
          onChange={e => set('collab_turns', e.target.value)}
          className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="2">2 (faster)</option>
          <option value="3">3 (thorough)</option>
          <option value="4">4</option>
          <option value="5">5</option>
        </select>
      </div>
      <div className="flex items-center gap-2">
        <input
          id="dry_run"
          type="checkbox"
          checked={fields.dry_run}
          onChange={e => set('dry_run', e.target.checked)}
          className="h-4 w-4 text-blue-600 border-gray-300 rounded"
        />
        <label htmlFor="dry_run" className="text-xs font-medium text-gray-700">Dry run (no API calls)</label>
      </div>
      <button type="submit" className="w-full bg-blue-600 text-white py-2 px-4 rounded text-sm font-medium hover:bg-blue-700 transition-colors">
        Launch Session
      </button>
    </form>
  )
}

function LaunchPanel({ onDispatch }) {
  const [activeTab, setActiveTab] = useState('Prelim')
  const tabs = ['Prelim', 'Deep', 'Session']

  return (
    <div className="bg-white shadow-sm rounded-lg p-5">
      <h2 className="text-sm font-semibold text-gray-900 mb-4">Launch Run</h2>
      <div className="flex gap-1 mb-5 border-b border-gray-200">
        {tabs.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
      {activeTab === 'Prelim' && <PrelimForm onDispatch={onDispatch} />}
      {activeTab === 'Deep' && <DeepForm onDispatch={onDispatch} />}
      {activeTab === 'Session' && <SessionForm onDispatch={onDispatch} />}
    </div>
  )
}

// ─── Main Dashboard ──────────────────────────────────────────────────────────

export default function Dashboard({ user, onLogout }) {
  const [runs, setRuns] = useState([])
  const [runsLoading, setRunsLoading] = useState(true)
  const [runsError, setRunsError] = useState(null)
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const [toast, setToast] = useState(null)
  const [dispatching, setDispatching] = useState(false)

  const fetchRuns = useCallback(async () => {
    try {
      const data = await listRuns(30)
      const sorted = (data.workflow_runs || []).sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at)
      )
      setRuns(sorted)
      setLastRefreshed(new Date())
      setRunsError(null)
    } catch (err) {
      setRunsError(err.message)
    } finally {
      setRunsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRuns()
    const id = setInterval(fetchRuns, 30000)
    return () => clearInterval(id)
  }, [fetchRuns])

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  async function handleDispatch(workflowFile, inputs) {
    setDispatching(true)
    try {
      await dispatchWorkflow(workflowFile, inputs)
      showToast('Run dispatched! It will appear below shortly.')
      setTimeout(fetchRuns, 3000)
    } catch (err) {
      showToast(err.message || 'Failed to dispatch workflow.', 'error')
    } finally {
      setDispatching(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav */}
      <nav className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 flex items-center justify-between">
        <span className="text-base font-semibold text-gray-900">AgentOrg</span>
        <div className="flex items-center gap-3">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt="" className="w-7 h-7 rounded-full" />
          )}
          <span className="text-sm text-gray-700 hidden sm:block">{user?.name || user?.login}</span>
          <button
            onClick={onLogout}
            className="text-sm text-gray-500 hover:text-gray-700 border border-gray-300 rounded px-3 py-1 hover:bg-gray-50 transition-colors"
          >
            Sign out
          </button>
        </div>
      </nav>

      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 max-w-sm px-4 py-3 rounded-lg shadow-lg text-sm font-medium ${
          toast.type === 'error'
            ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-green-50 border border-green-200 text-green-700'
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Dispatching overlay indicator */}
      {dispatching && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-white border border-gray-200 shadow-lg rounded-lg px-4 py-2 flex items-center gap-2 text-sm text-gray-600">
          <Spinner className="h-4 w-4 text-blue-600" />
          Dispatching workflow...
        </div>
      )}

      {/* Body */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Recent Runs — takes 2 of 3 columns */}
          <div className="lg:col-span-2">
            <div className="bg-white shadow-sm rounded-lg">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">Recent Runs</h2>
                <div className="flex items-center gap-3">
                  {lastRefreshed && (
                    <span className="text-xs text-gray-400">
                      Updated {lastRefreshed.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  )}
                  <button
                    onClick={() => { setRunsLoading(true); fetchRuns() }}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    {runsLoading ? <Spinner className="h-3 w-3" /> : null}
                    Refresh
                  </button>
                </div>
              </div>

              {runsError && (
                <div className="px-5 py-4 text-sm text-red-600">
                  Error loading runs: {runsError}
                </div>
              )}

              {!runsError && runsLoading && runs.length === 0 && (
                <div className="px-5 py-8 text-sm text-gray-400 text-center flex items-center justify-center gap-2">
                  <Spinner className="h-4 w-4" />
                  Loading runs...
                </div>
              )}

              {!runsError && !runsLoading && runs.length === 0 && (
                <div className="px-5 py-8 text-sm text-gray-400 text-center">
                  No runs found.
                </div>
              )}

              {runs.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs font-medium text-gray-500 border-b border-gray-100">
                        <th className="px-5 py-2.5 text-left">Workflow</th>
                        <th className="px-3 py-2.5 text-left">Name</th>
                        <th className="px-3 py-2.5 text-left">Status</th>
                        <th className="px-3 py-2.5 text-left whitespace-nowrap">Started</th>
                        <th className="px-3 py-2.5 text-left">Duration</th>
                        <th className="px-3 py-2.5 text-left"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {runs.map(run => {
                        const wf = workflowLabel(run.name)
                        return (
                          <tr key={run.id} className="hover:bg-gray-50 transition-colors">
                            <td className="px-5 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${wf.color}`}>
                                {wf.label}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-gray-700 max-w-xs truncate" title={run.display_title || run.name}>
                              {run.display_title || run.name}
                            </td>
                            <td className="px-3 py-3">
                              <StatusBadge status={run.status} conclusion={run.conclusion} />
                            </td>
                            <td className="px-3 py-3 text-gray-500 whitespace-nowrap text-xs">
                              {formatStarted(run.run_started_at || run.created_at)}
                            </td>
                            <td className="px-3 py-3 text-gray-500 text-xs whitespace-nowrap">
                              {formatDuration(run)}
                            </td>
                            <td className="px-3 py-3">
                              <a
                                href={run.html_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-600 hover:underline whitespace-nowrap"
                              >
                                Results →
                              </a>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* Launch Panel — 1 of 3 columns */}
          <div className="lg:col-span-1">
            <LaunchPanel onDispatch={handleDispatch} />
          </div>

        </div>
      </div>
    </div>
  )
}
