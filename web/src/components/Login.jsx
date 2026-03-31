import { useState } from 'react'
import { setToken, validateToken } from '../lib/github.js'

export default function Login({ onLogin }) {
  const [pat, setPat] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [validatedUser, setValidatedUser] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!pat.trim()) return
    setLoading(true)
    setError(null)
    setValidatedUser(null)
    try {
      setToken(pat.trim())
      const user = await validateToken()
      setValidatedUser(user)
      setTimeout(() => onLogin(user), 800)
    } catch (err) {
      setError(err.message || 'Invalid token. Check that it has the workflow scope.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white shadow-sm rounded-lg p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-gray-900">AgentOrg</h1>
            <p className="text-sm text-gray-500 mt-1">Research automation by baileymcintosh</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label htmlFor="pat" className="block text-sm font-medium text-gray-700 mb-1">
                GitHub Personal Access Token
              </label>
              <input
                id="pat"
                type="password"
                value={pat}
                onChange={(e) => setPat(e.target.value)}
                placeholder="ghp_..."
                autoComplete="off"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                disabled={loading}
              />
              <div className="mt-2 text-xs text-gray-500 space-y-1">
                <p>Required scopes:</p>
                <ul className="ml-3 space-y-0.5 list-disc list-inside">
                  <li>Classic PAT: <span className="font-mono bg-gray-100 px-1 rounded">workflow</span></li>
                  <li>Fine-grained: Actions — Read &amp; Write</li>
                </ul>
                <a
                  href="https://github.com/settings/tokens/new?scopes=workflow"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block mt-1 text-blue-600 hover:underline"
                >
                  Generate a token →
                </a>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-md px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            {validatedUser && (
              <div className="bg-green-50 border border-green-200 rounded-md px-3 py-2 text-sm text-green-700 flex items-center gap-2">
                {validatedUser.avatar_url && (
                  <img src={validatedUser.avatar_url} alt="" className="w-5 h-5 rounded-full" />
                )}
                <span>Signed in as <strong>{validatedUser.name || validatedUser.login}</strong></span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !pat.trim()}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {loading && (
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
              {loading ? 'Verifying...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
