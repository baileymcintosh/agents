import { useState, useEffect } from 'react'
import { listRepos, readRepoFile, listRuns, cached } from '../lib/github.js'

function formatProjectName(repoName) {
  return repoName
    .split('-')
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function StatusDot({ status }) {
  const colors = {
    success: 'bg-green-500',
    in_progress: 'bg-yellow-500 animate-pulse',
    queued: 'bg-yellow-500 animate-pulse',
    failure: 'bg-red-500',
    unknown: 'bg-gray-400',
  }
  const color = colors[status] || colors.unknown
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
}

function SkeletonCard() {
  return (
    <div className="bg-white shadow-sm rounded-xl p-5 space-y-3 animate-pulse">
      <div className="flex items-start justify-between">
        <div className="h-4 bg-gray-200 rounded w-2/3" />
        <div className="h-2.5 w-2.5 bg-gray-200 rounded-full" />
      </div>
      <div className="space-y-2">
        <div className="h-3 bg-gray-200 rounded w-full" />
        <div className="h-3 bg-gray-200 rounded w-4/5" />
      </div>
      <div className="flex items-center justify-between pt-1">
        <div className="h-3 bg-gray-200 rounded w-1/4" />
        <div className="h-7 bg-gray-200 rounded w-16" />
      </div>
    </div>
  )
}

function ExternalLinkIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
    </svg>
  )
}

async function chunkAll(items, size, fn) {
  const results = []
  for (let i = 0; i < items.length; i += size) {
    const chunk = items.slice(i, i + size)
    const chunkResults = await Promise.all(chunk.map(fn))
    results.push(...chunkResults)
  }
  return results
}

export default function ProjectLibrary({ navigate }) {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [runStatuses, setRunStatuses] = useState({})

  useEffect(() => {
    loadProjects()
  }, [])

  async function loadProjects() {
    setLoading(true)
    setError(null)
    try {
      const projectList = await cached('project_list', 3 * 60 * 1000, async () => {
        const repos = await listRepos()
        // Filter out the agents repo itself
        const candidates = (repos || []).filter(r => r.name !== 'agents')

        // Check each repo for BRIEF.md in batches of 10
        const checked = await chunkAll(candidates, 10, async (repo) => {
          const brief = await readRepoFile(repo.name, 'BRIEF.md')
          if (!brief) return null
          return { repo, brief }
        })

        return checked.filter(Boolean)
      })

      setProjects(projectList)

      // Load run statuses for each project
      loadRunStatuses(projectList)
    } catch (err) {
      setError(err.message || 'Failed to load projects.')
    } finally {
      setLoading(false)
    }
  }

  async function loadRunStatuses(projectList) {
    try {
      const data = await listRuns(40)
      const runs = data?.workflow_runs || []
      const statuses = {}
      for (const { repo } of projectList) {
        // Try to find runs that reference this repo name
        const matching = runs.filter(r =>
          (r.display_title || '').toLowerCase().includes(repo.name.toLowerCase()) ||
          (r.name || '').toLowerCase().includes(repo.name.toLowerCase())
        )
        if (matching.length > 0) {
          const latest = matching[0]
          if (latest.status === 'in_progress' || latest.status === 'queued') {
            statuses[repo.name] = 'in_progress'
          } else if (latest.status === 'completed') {
            statuses[repo.name] = latest.conclusion === 'success' ? 'success' : 'failure'
          } else {
            statuses[repo.name] = 'unknown'
          }
        } else {
          statuses[repo.name] = 'unknown'
        }
      }
      setRunStatuses(statuses)
    } catch {
      // run statuses are best-effort
    }
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Your Projects</h1>
        <button
          onClick={() => navigate('new', {})}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          New Project
        </button>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      )}

      {/* Empty state */}
      {!loading && projects.length === 0 && (
        <div className="text-center py-20">
          <div className="text-gray-400 text-base mb-2">No projects yet.</div>
          <p className="text-sm text-gray-400 mb-6">Launch your first research run to get started.</p>
          <button
            onClick={() => navigate('new', {})}
            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            New Project
          </button>
        </div>
      )}

      {/* Project grid */}
      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {projects.map(({ repo, brief }) => {
            const excerpt = brief ? brief.replace(/^#+\s.*$/m, '').trim().slice(0, 120) : ''
            const status = runStatuses[repo.name] || 'unknown'
            return (
              <div
                key={repo.name}
                className="bg-white shadow-sm rounded-xl p-5 flex flex-col gap-3 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between gap-2">
                  <h2 className="text-base font-semibold text-gray-900 leading-snug">
                    {formatProjectName(repo.name)}
                  </h2>
                  <StatusDot status={status} />
                </div>

                {excerpt && (
                  <p className="text-sm text-gray-500 leading-relaxed flex-1">
                    {excerpt}{brief && brief.length > 120 ? '…' : ''}
                  </p>
                )}

                <div className="flex items-center justify-between mt-auto pt-1">
                  <span className="text-xs text-gray-400">{formatDate(repo.updated_at)}</span>
                  <div className="flex items-center gap-2">
                    <a
                      href={repo.html_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-400 hover:text-gray-600 transition-colors"
                      title="Open on GitHub"
                    >
                      <ExternalLinkIcon />
                    </a>
                    <button
                      onClick={() => navigate('project', { repoName: repo.name })}
                      className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                    >
                      Open
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
