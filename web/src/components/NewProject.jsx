import { useState, useEffect } from 'react'
import { dispatchWorkflow } from '../lib/github.js'

const HISTORY_KEY = 'agentorg_brief_history'

function getHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}

function saveToHistory(entry) {
  const history = getHistory()
  const updated = [entry, ...history.filter(h => h.id !== entry.id)].slice(0, 20)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated))
}

function deleteFromHistory(id) {
  const updated = getHistory().filter(h => h.id !== id)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(updated))
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 50)
}

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

const DEPTH_OPTIONS = [
  {
    id: 'prelim',
    label: 'Prelim',
    time: '8–15 min',
    cost: '~$0.30–0.80',
    badge: 'bg-purple-100 text-purple-700 border-purple-200',
    activeBorder: 'border-purple-500 bg-purple-50',
    workflow: 'prelim.yml',
  },
  {
    id: 'deep',
    label: 'Deep',
    time: '45–90 min',
    cost: '~$3–8',
    badge: 'bg-blue-100 text-blue-700 border-blue-200',
    activeBorder: 'border-blue-500 bg-blue-50',
    workflow: 'deep.yml',
  },
  {
    id: 'session',
    label: 'Session',
    time: 'custom budget',
    cost: '~$2–20',
    badge: 'bg-orange-100 text-orange-700 border-orange-200',
    activeBorder: 'border-orange-500 bg-orange-50',
    workflow: 'research_session.yml',
  },
]

export default function NewProject({ navigate, onToast }) {
  const [brief, setBrief] = useState('')
  const [depth, setDepth] = useState('prelim')
  const [timeBudget, setTimeBudget] = useState('2h')
  const [modelTier, setModelTier] = useState('sonnet')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [slug, setSlug] = useState('')
  const [slugManual, setSlugManual] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [history, setHistory] = useState(getHistory())

  useEffect(() => {
    if (!slugManual) setSlug(slugify(brief.split('\n')[0]))
  }, [brief, slugManual])

  const selectedDepth = DEPTH_OPTIONS.find(d => d.id === depth)

  function loadFromHistory(entry) {
    setBrief(entry.brief)
    setDepth(entry.depth)
    setTimeBudget(entry.timeBudget || '2h')
    setModelTier(entry.modelTier || 'sonnet')
    setSlug(entry.slug || '')
    setSlugManual(!!entry.slug)
    window.scrollTo(0, 0)
  }

  function handleDelete(id) {
    deleteFromHistory(id)
    setHistory(getHistory())
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!brief.trim()) return
    setSubmitting(true)
    try {
      const entry = {
        id: Date.now().toString(),
        brief: brief.trim(),
        depth,
        timeBudget,
        modelTier,
        slug: slug.trim(),
        createdAt: new Date().toISOString(),
      }
      const inputs = {
        project_name: slug.trim() || slugify(brief.split('\n')[0]) || 'research',
        brief: brief.trim(),
      }
      if (slug.trim()) inputs.repo_name = slug.trim()
      if (depth === 'session') {
        inputs.time_budget = timeBudget
        inputs.model_tier = modelTier
        inputs.collab_turns = '3'
        inputs.dry_run = 'false'
      }
      await dispatchWorkflow(selectedDepth.workflow, inputs)
      saveToHistory(entry)
      setHistory(getHistory())
      onToast(`${selectedDepth.label} run dispatched! Check Active Runs for status.`)
      navigate('active-runs', {})
    } catch (err) {
      onToast(err.message || 'Failed to dispatch workflow.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Main input */}
        <div className="bg-white shadow-sm rounded-xl p-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            What do you want researched?
          </label>
          <textarea
            required
            autoFocus
            rows={6}
            value={brief}
            onChange={e => setBrief(e.target.value)}
            placeholder="Describe what you want to know. Be as specific or as open-ended as you like — the agents will figure out the angles.

e.g. Analyze the economic relationship between Iran and the US through 2026, focusing on sanctions regimes, oil market effects, and what a normalization scenario would mean for EM assets."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none leading-relaxed"
          />
        </div>

        {/* Depth selector */}
        <div className="bg-white shadow-sm rounded-xl p-5">
          <label className="block text-sm font-medium text-gray-700 mb-3">Depth</label>
          <div className="grid grid-cols-3 gap-3">
            {DEPTH_OPTIONS.map(opt => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setDepth(opt.id)}
                className={`p-3 rounded-xl border-2 text-left transition-all ${
                  depth === opt.id ? opt.activeBorder : 'border-gray-200 hover:border-gray-300 bg-white'
                }`}
              >
                <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border mb-2 ${opt.badge}`}>
                  {opt.label}
                </span>
                <div className="text-xs font-medium text-gray-800">{opt.time}</div>
                <div className="text-xs text-gray-400 mt-0.5">{opt.cost}</div>
              </button>
            ))}
          </div>

          {/* Session-specific options */}
          {depth === 'session' && (
            <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-100">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Time budget</label>
                <input
                  type="text"
                  value={timeBudget}
                  onChange={e => setTimeBudget(e.target.value)}
                  placeholder="2h"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-400 mt-1">e.g. 30m, 2h, 6h</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Model tier</label>
                <select
                  value={modelTier}
                  onChange={e => setModelTier(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                >
                  <option value="sonnet">sonnet (~$1–3 / 2h)</option>
                  <option value="opus">opus (~$7–10 / 2h)</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Advanced */}
        <div className="bg-white shadow-sm rounded-xl px-5 py-3">
          <button
            type="button"
            onClick={() => setShowAdvanced(a => !a)}
            className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors w-full"
          >
            <svg className={`h-3 w-3 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Advanced
          </button>
          {showAdvanced && (
            <div className="mt-3">
              <label className="block text-xs font-medium text-gray-600 mb-1">Project ID (GitHub repo name)</label>
              <input
                type="text"
                value={slug}
                onChange={e => { setSlug(e.target.value); setSlugManual(true) }}
                placeholder="auto-generated from brief"
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400 mt-1">Leave blank to auto-generate. Determines the GitHub repo name.</p>
            </div>
          )}
        </div>

        {/* Submit */}
        <div>
          <button
            type="submit"
            disabled={submitting || !brief.trim()}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-3 px-4 rounded-xl text-sm font-semibold transition-colors flex items-center justify-center gap-2"
          >
            {submitting && (
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            Launch {selectedDepth?.label} Run
          </button>
          <p className="text-xs text-center text-gray-400 mt-2">
            {selectedDepth?.cost} · {selectedDepth?.time}
          </p>
        </div>
      </form>

      {/* Brief history */}
      {history.length > 0 && (
        <div className="mt-10">
          <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Recent</h2>
          <div className="space-y-2">
            {history.map(entry => {
              const depthOpt = DEPTH_OPTIONS.find(d => d.id === entry.depth)
              const preview = entry.brief.replace(/\n/g, ' ').slice(0, 90)
              return (
                <div
                  key={entry.id}
                  className="bg-white shadow-sm rounded-xl px-4 py-3 flex items-start gap-3 hover:shadow-md transition-shadow"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-700 leading-snug truncate" title={entry.brief}>
                      {preview}{entry.brief.length > 90 ? '…' : ''}
                    </p>
                    <div className="flex items-center gap-2 mt-1.5">
                      {depthOpt && (
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${depthOpt.badge}`}>
                          {depthOpt.label}
                        </span>
                      )}
                      <span className="text-xs text-gray-400">{formatDate(entry.createdAt)}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => loadFromHistory(entry)}
                      className="text-xs text-blue-600 hover:text-blue-700 font-medium border border-blue-200 hover:border-blue-300 px-2.5 py-1 rounded-lg transition-colors"
                    >
                      Rerun
                    </button>
                    <button
                      onClick={() => handleDelete(entry.id)}
                      className="text-gray-300 hover:text-red-400 transition-colors p-1"
                      title="Remove"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
