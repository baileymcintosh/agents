import { useState, useEffect } from 'react'
import { dispatchWorkflow } from '../lib/github.js'

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
}

const DEPTH_OPTIONS = [
  {
    id: 'prelim',
    label: 'Prelim',
    description: 'Quick proof-of-concept',
    time: '8-15 min',
    cost: '~$0.30-0.80',
    badge: 'bg-purple-100 text-purple-700',
    workflow: 'prelim.yml',
  },
  {
    id: 'deep',
    label: 'Deep',
    description: 'Full research memo',
    time: '45-90 min',
    cost: '~$3-8',
    badge: 'bg-blue-100 text-blue-700',
    workflow: 'deep.yml',
  },
  {
    id: 'session',
    label: 'Session',
    description: 'Multi-cycle deep dive',
    time: 'custom budget',
    cost: '~$2-20',
    badge: 'bg-orange-100 text-orange-700',
    workflow: 'research_session.yml',
  },
]

function buildMarkdownBrief({ topic, questions, context, angle }) {
  const lines = []
  lines.push(`# ${topic || 'Untitled'}`)
  lines.push('')
  if (questions.filter(q => q.trim()).length > 0) {
    lines.push('## Research Questions')
    questions.filter(q => q.trim()).forEach(q => lines.push(`- ${q}`))
    lines.push('')
  }
  if (context.trim()) {
    lines.push('## Context')
    lines.push(context.trim())
    lines.push('')
  }
  if (angle.trim()) {
    lines.push('## Angle')
    lines.push(angle.trim())
    lines.push('')
  }
  return lines.join('\n')
}

export default function NewProject({ navigate, onToast }) {
  const [topic, setTopic] = useState('')
  const [questions, setQuestions] = useState(['', ''])
  const [context, setContext] = useState('')
  const [angle, setAngle] = useState('')
  const [depth, setDepth] = useState('prelim')
  const [timeBudget, setTimeBudget] = useState('2h')
  const [modelTier, setModelTier] = useState('sonnet')
  const [slug, setSlug] = useState('')
  const [slugManual, setSlugManual] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!slugManual) {
      setSlug(slugify(topic))
    }
  }, [topic, slugManual])

  function addQuestion() {
    setQuestions(qs => [...qs, ''])
  }

  function setQuestion(idx, val) {
    setQuestions(qs => qs.map((q, i) => (i === idx ? val : q)))
  }

  function removeQuestion(idx) {
    setQuestions(qs => qs.filter((_, i) => i !== idx))
  }

  const selectedDepth = DEPTH_OPTIONS.find(d => d.id === depth)
  const brief = buildMarkdownBrief({ topic, questions, context, angle })

  async function handleSubmit(e) {
    e.preventDefault()
    if (!topic.trim()) return
    setSubmitting(true)
    try {
      const inputs = {
        project_name: topic.trim(),
        brief: brief.trim(),
      }
      if (slug.trim()) {
        inputs.repo_name = slug.trim()
      }
      if (depth === 'session') {
        inputs.time_budget = timeBudget
        inputs.model_tier = modelTier
      }
      await dispatchWorkflow(selectedDepth.workflow, inputs)
      onToast(`${selectedDepth.label} run dispatched! Check Active Runs for status.`)
      navigate('library', {})
    } catch (err) {
      onToast(err.message || 'Failed to dispatch workflow.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Project</h1>

      <form onSubmit={handleSubmit}>
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left panel: structured builder */}
          <div className="flex-1 space-y-6">

            {/* What to research */}
            <div className="bg-white shadow-sm rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">What to research</h2>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Research topic <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                  placeholder="Iran-US economic relations through 2026"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Key questions</label>
                <div className="space-y-2">
                  {questions.map((q, idx) => (
                    <div key={idx} className="flex gap-2">
                      <input
                        type="text"
                        value={q}
                        onChange={e => setQuestion(idx, e.target.value)}
                        placeholder={`Question ${idx + 1}`}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      {questions.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeQuestion(idx)}
                          className="text-gray-400 hover:text-red-500 transition-colors px-1"
                          title="Remove question"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={addQuestion}
                  className="mt-2 text-sm text-blue-600 hover:underline"
                >
                  + Add question
                </button>
              </div>
            </div>

            {/* Context */}
            <div className="bg-white shadow-sm rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">Context</h2>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  What decisions will this inform?
                </label>
                <textarea
                  rows={2}
                  value={context}
                  onChange={e => setContext(e.target.value)}
                  placeholder="e.g. Investment thesis for EM exposure, policy analysis for a think tank..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Any specific angle or hypothesis?
                </label>
                <textarea
                  rows={2}
                  value={angle}
                  onChange={e => setAngle(e.target.value)}
                  placeholder="e.g. Hypothesis: sanctions relief will accelerate faster than market consensus expects..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                />
              </div>
            </div>

            {/* Run settings */}
            <div className="bg-white shadow-sm rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-semibold text-gray-900">Run settings</h2>

              {/* Depth selector */}
              <div className="grid grid-cols-3 gap-3">
                {DEPTH_OPTIONS.map(opt => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setDepth(opt.id)}
                    className={`p-3 rounded-xl border-2 text-left transition-all ${
                      depth === opt.id
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold mb-2 ${opt.badge}`}>
                      {opt.label}
                    </div>
                    <div className="text-xs font-medium text-gray-900 leading-snug">{opt.description}</div>
                    <div className="text-xs text-gray-500 mt-1">{opt.time}</div>
                    <div className="text-xs text-gray-400">{opt.cost}</div>
                  </button>
                ))}
              </div>

              {/* Session-specific fields */}
              {depth === 'session' && (
                <div className="grid grid-cols-2 gap-4 pt-1">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Time budget</label>
                    <input
                      type="text"
                      value={timeBudget}
                      onChange={e => setTimeBudget(e.target.value)}
                      placeholder="2h"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <p className="text-xs text-gray-400 mt-1">e.g. 30m, 2h, 6h</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Model tier</label>
                    <select
                      value={modelTier}
                      onChange={e => setModelTier(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    >
                      <option value="sonnet">sonnet (~$1-3 / 2h)</option>
                      <option value="opus">opus (~$7-10 / 2h)</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Project slug */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Project ID</label>
                <input
                  type="text"
                  value={slug}
                  onChange={e => { setSlug(e.target.value); setSlugManual(true) }}
                  placeholder="auto-generated from topic"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-400 mt-1">Used as the GitHub repo name. Auto-filled from topic.</p>
              </div>
            </div>

            {/* Submit */}
            <div>
              <button
                type="submit"
                disabled={submitting || !topic.trim()}
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
                Estimated cost: {selectedDepth?.cost} · {selectedDepth?.time}
              </p>
            </div>

          </div>

          {/* Right panel: brief preview */}
          <div className="lg:w-96 xl:w-[420px]">
            <div className="bg-white shadow-sm rounded-xl p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Brief Preview</h2>
              <div className="bg-gray-50 rounded-lg p-4 min-h-64 max-h-[600px] overflow-y-auto">
                <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {brief || '# Your research topic\n\n## Research Questions\n- ...\n\n## Context\n...\n\n## Angle\n...'}
                </pre>
              </div>
            </div>
          </div>

        </div>
      </form>
    </div>
  )
}
