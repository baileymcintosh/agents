import { useState, useEffect } from 'react'
import { getToken, validateToken, clearToken } from './lib/github.js'
import Login from './components/Login.jsx'
import Dashboard from './components/Dashboard.jsx'

export default function App() {
  const [screen, setScreen] = useState('loading')
  const [user, setUser] = useState(null)

  useEffect(() => {
    const token = getToken()
    if (!token) {
      setScreen('login')
      return
    }
    validateToken()
      .then((u) => {
        setUser(u)
        setScreen('dashboard')
      })
      .catch(() => {
        clearToken()
        setScreen('login')
      })
  }, [])

  function handleLogin(u) {
    setUser(u)
    setScreen('dashboard')
  }

  function handleLogout() {
    clearToken()
    setUser(null)
    setScreen('login')
  }

  if (screen === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-500">
          <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-sm">Verifying token...</span>
        </div>
      </div>
    )
  }

  if (screen === 'login') {
    return <Login onLogin={handleLogin} />
  }

  return <Dashboard user={user} onLogout={handleLogout} />
}
