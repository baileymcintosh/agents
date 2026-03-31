import { useState, useEffect, useCallback } from 'react'
import {
  getToken, setToken, validateToken, clearToken,
  clearCache, listRuns, exchangeOAuthCode,
} from './lib/github.js'
import Login from './components/Login.jsx'
import Sidebar from './components/Sidebar.jsx'
import ProjectLibrary from './components/ProjectLibrary.jsx'
import NewProject from './components/NewProject.jsx'
import ProjectDetail from './components/ProjectDetail.jsx'
import ReportReader from './components/ReportReader.jsx'
import ActiveRuns from './components/ActiveRuns.jsx'

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function SettingsScreen({ user, onLogout }) {
  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Settings</h1>
      <div className="bg-white shadow-sm rounded-xl p-5 space-y-5">
        <div className="flex items-center gap-3">
          {user?.avatar_url && (
            <img src={user.avatar_url} alt="" className="w-10 h-10 rounded-full" />
          )}
          <div>
            <p className="text-sm font-semibold text-gray-900">{user?.name || user?.login}</p>
            <p className="text-xs text-gray-500">@{user?.login}</p>
          </div>
        </div>
        <hr className="border-gray-100" />
        <div className="flex flex-col gap-3">
          <button
            onClick={() => { clearCache(); window.location.reload() }}
            className="w-full text-left px-4 py-2.5 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Clear cache &amp; reload
          </button>
          <button
            onClick={onLogout}
            className="w-full text-left px-4 py-2.5 border border-red-200 rounded-lg text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  // 'loading' | 'oauth-callback' | 'login' | 'app'
  const [appState, setAppState] = useState('loading')
  const [user, setUser] = useState(null)
  const [nav, setNav] = useState({ screen: 'library', params: {} })
  const [toast, setToast] = useState(null)
  const [activeRunCount, setActiveRunCount] = useState(0)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')

    // GitHub redirected back with an OAuth code — exchange it
    if (code) {
      // Clean the URL immediately so a refresh doesn't re-use the code
      window.history.replaceState({}, document.title, '/')
      setAppState('oauth-callback')
      exchangeOAuthCode(code)
        .then(token => {
          setToken(token)
          return validateToken()
        })
        .then(u => {
          setUser(u)
          setAppState('app')
        })
        .catch(() => {
          setAppState('login')
        })
      return
    }

    // Normal load — check for stored token
    const token = getToken()
    if (!token) {
      setAppState('login')
      return
    }
    validateToken()
      .then(u => {
        setUser(u)
        setAppState('app')
      })
      .catch(() => {
        clearToken()
        setAppState('login')
      })
  }, [])

  // Poll active run count for sidebar badge
  const pollActiveRuns = useCallback(async () => {
    try {
      const data = await listRuns(40)
      const active = (data?.workflow_runs || []).filter(
        r => r.status === 'in_progress' || r.status === 'queued'
      )
      setActiveRunCount(active.length)
    } catch { /* best effort */ }
  }, [])

  useEffect(() => {
    if (appState !== 'app') return
    pollActiveRuns()
    const id = setInterval(pollActiveRuns, 30000)
    return () => clearInterval(id)
  }, [appState, pollActiveRuns])

  function navigate(screen, params = {}) {
    setNav({ screen, params })
    window.scrollTo(0, 0)
  }

  function handleLogout() {
    clearToken()
    clearCache()
    setUser(null)
    setAppState('login')
  }

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  if (appState === 'loading' || appState === 'oauth-callback') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-500">
          <Spinner />
          <span className="text-sm">
            {appState === 'oauth-callback' ? 'Signing in...' : 'Loading...'}
          </span>
        </div>
      </div>
    )
  }

  if (appState === 'login') {
    return <Login />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar
        user={user}
        screen={nav.screen}
        navigate={navigate}
        onLogout={handleLogout}
        activeRunCount={activeRunCount}
      />

      <div className="lg:pl-60 pt-14 lg:pt-0">
        <main className="min-h-screen bg-gray-50">
          {nav.screen === 'library' && <ProjectLibrary navigate={navigate} />}
          {nav.screen === 'new' && <NewProject navigate={navigate} onToast={showToast} />}
          {nav.screen === 'project' && <ProjectDetail params={nav.params} navigate={navigate} onToast={showToast} />}
          {nav.screen === 'report' && <ReportReader params={nav.params} navigate={navigate} onToast={showToast} />}
          {nav.screen === 'active-runs' && <ActiveRuns />}
          {nav.screen === 'settings' && <SettingsScreen user={user} onLogout={handleLogout} />}
        </main>
      </div>

      {toast && (
        <div className={`fixed top-4 right-4 z-50 max-w-sm px-4 py-3 rounded-xl shadow-lg text-sm font-medium ${
          toast.type === 'error'
            ? 'bg-red-50 border border-red-200 text-red-700'
            : 'bg-green-50 border border-green-200 text-green-700'
        }`}>
          {toast.msg}
        </div>
      )}
    </div>
  )
}
