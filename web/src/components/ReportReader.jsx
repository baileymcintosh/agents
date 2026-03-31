import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { readRepoFile, dispatchWorkflow } from '../lib/github.js'

function formatProjectName(repoName) {
  return repoName
    .split('-')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// Prose component styles applied via inline components
const proseComponents = {
  h1: ({ children }) => (
    <h1 style={{ fontSize: '1.875rem', fontWeight: 700, marginTop: '2rem', marginBottom: '1rem', color: '#111827', lineHeight: 1.25 }}>
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginTop: '1.5rem', marginBottom: '0.75rem', paddingBottom: '0.5rem', borderBottom: '1px solid #e5e7eb', color: '#1f2937' }}>
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginTop: '1rem', marginBottom: '0.5rem', color: '#1f2937' }}>
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 style={{ fontSize: '1.125rem', fontWeight: 600, marginTop: '0.75rem', marginBottom: '0.5rem', color: '#374151' }}>
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p style={{ marginBottom: '1rem', lineHeight: 1.75, color: '#374151' }}>
      {children}
    </p>
  ),
  ul: ({ children }) => (
    <ul style={{ marginBottom: '1rem', paddingLeft: '1.5rem', listStyleType: 'disc' }}>
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol style={{ marginBottom: '1rem', paddingLeft: '1.5rem', listStyleType: 'decimal' }}>
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li style={{ marginBottom: '0.25rem', lineHeight: 1.625, color: '#374151' }}>
      {children}
    </li>
  ),
  strong: ({ children }) => (
    <strong style={{ fontWeight: 600, color: '#111827' }}>
      {children}
    </strong>
  ),
  em: ({ children }) => (
    <em style={{ fontStyle: 'italic' }}>
      {children}
    </em>
  ),
  blockquote: ({ children }) => (
    <blockquote style={{ borderLeft: '4px solid #d1d5db', paddingLeft: '1rem', fontStyle: 'italic', color: '#6b7280', margin: '1rem 0' }}>
      {children}
    </blockquote>
  ),
  code: ({ inline, children }) => {
    if (inline) {
      return (
        <code style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.875rem', backgroundColor: '#f3f4f6', padding: '0.125rem 0.375rem', borderRadius: '0.25rem', color: '#1f2937' }}>
          {children}
        </code>
      )
    }
    return (
      <pre style={{ backgroundColor: '#f3f4f6', padding: '1rem', borderRadius: '0.5rem', overflowX: 'auto', marginBottom: '1rem' }}>
        <code style={{ fontFamily: 'ui-monospace, monospace', fontSize: '0.875rem', color: '#1f2937' }}>
          {children}
        </code>
      </pre>
    )
  },
  table: ({ children }) => (
    <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead style={{ backgroundColor: '#f9fafb' }}>
      {children}
    </thead>
  ),
  th: ({ children }) => (
    <th style={{ padding: '0.625rem 0.75rem', textAlign: 'left', fontWeight: 600, color: '#374151', borderBottom: '2px solid #e5e7eb' }}>
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td style={{ padding: '0.625rem 0.75rem', color: '#4b5563', borderBottom: '1px solid #f3f4f6' }}>
      {children}
    </td>
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', textDecoration: 'underline' }}>
      {children}
    </a>
  ),
  hr: () => (
    <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '2rem 0' }} />
  ),
}

export default function ReportReader({ params, navigate, onToast }) {
  const repoName = params.repoName
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [iterating, setIterating] = useState(false)

  useEffect(() => {
    if (!repoName) return
    loadReport()
  }, [repoName])

  async function loadReport() {
    setLoading(true)
    setNotFound(false)
    const text = await readRepoFile(repoName, 'final_report.md')
    if (text) {
      setReport(text)
    } else {
      setNotFound(true)
    }
    setLoading(false)
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

  return (
    <div className="p-6">
      {/* Back nav */}
      <div className="max-w-860 mb-4" style={{ maxWidth: '860px', margin: '0 auto 1rem' }}>
        <button
          onClick={() => navigate('project', { repoName })}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to {formatProjectName(repoName)}
        </button>
      </div>

      <div style={{ maxWidth: '860px', margin: '0 auto' }}>
        {/* Loading */}
        {loading && (
          <div className="flex items-center justify-center py-20 gap-3 text-gray-400">
            <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="text-sm">Loading report...</span>
          </div>
        )}

        {/* Not found */}
        {!loading && notFound && (
          <div className="text-center py-20">
            <p className="text-gray-500 text-base mb-2">Report not yet available.</p>
            <p className="text-sm text-gray-400">Run the pipeline to generate one.</p>
            <button
              onClick={() => navigate('project', { repoName })}
              className="mt-4 text-sm text-blue-600 hover:underline"
            >
              Back to project
            </button>
          </div>
        )}

        {/* Report content */}
        {!loading && report && (
          <>
            <article className="bg-white shadow-sm rounded-xl px-8 py-8">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={proseComponents}
              >
                {report}
              </ReactMarkdown>
            </article>

            {/* Iterate section */}
            <div className="mt-8 pt-8 border-t border-gray-200">
              <h2 className="text-base font-semibold text-gray-900 mb-4">Iterate on this report</h2>
              <form onSubmit={handleIterate} className="space-y-3">
                <textarea
                  rows={4}
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="Feedback for next run: e.g. The sanctions analysis needs more depth. Also explore the banking sector angle..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
                <button
                  type="submit"
                  disabled={iterating}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2.5 px-5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
                >
                  {iterating && (
                    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  Launch Deep Run with feedback
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
