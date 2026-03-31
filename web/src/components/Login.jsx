import { useState } from 'react'
import { startDeviceFlow, pollDeviceFlow, setToken, validateToken } from '../lib/github.js'

function GitHubIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z" />
    </svg>
  )
}

function CopyIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  )
}

export default function Login({ onLogin }) {
  const [phase, setPhase] = useState('idle') // idle | starting | waiting | error
  const [userCode, setUserCode] = useState('')
  const [verificationUri, setVerificationUri] = useState('')
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  async function handleSignIn() {
    setPhase('starting')
    setError('')
    try {
      const flow = await startDeviceFlow()
      setUserCode(flow.user_code)
      setVerificationUri(flow.verification_uri)
      setPhase('waiting')

      // Open the GitHub device page automatically
      window.open(flow.verification_uri, '_blank', 'noopener,noreferrer')

      // Poll until authorized or expired
      const token = await pollDeviceFlow(flow.device_code, flow.interval)
      setToken(token)
      const user = await validateToken()
      onLogin(user)
    } catch (err) {
      setError(err.message || 'Sign in failed. Please try again.')
      setPhase('error')
    }
  }

  function copyCode() {
    navigator.clipboard.writeText(userCode).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  function retry() {
    setPhase('idle')
    setError('')
    setUserCode('')
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-white shadow-sm rounded-2xl p-8 text-center">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-gray-900">AgentOrg</h1>
            <p className="text-sm text-gray-400 mt-1">Research automation</p>
          </div>

          {/* idle */}
          {phase === 'idle' && (
            <button
              onClick={handleSignIn}
              className="w-full flex items-center justify-center gap-2.5 bg-gray-900 hover:bg-gray-800 text-white py-2.5 px-4 rounded-xl text-sm font-semibold transition-colors"
            >
              <GitHubIcon />
              Sign in with GitHub
            </button>
          )}

          {/* starting */}
          {phase === 'starting' && (
            <div className="flex items-center justify-center gap-2 text-gray-400 py-4">
              <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span className="text-sm">Connecting to GitHub...</span>
            </div>
          )}

          {/* waiting — show the code */}
          {phase === 'waiting' && (
            <div className="space-y-5">
              <div>
                <p className="text-sm text-gray-600 mb-3">
                  A GitHub tab just opened. Enter this code there:
                </p>
                <div className="flex items-center justify-center gap-2">
                  <span className="text-3xl font-mono font-bold tracking-widest text-gray-900 bg-gray-50 border border-gray-200 rounded-xl px-5 py-3">
                    {userCode}
                  </span>
                  <button
                    onClick={copyCode}
                    title="Copy code"
                    className="text-gray-400 hover:text-gray-600 transition-colors p-2"
                  >
                    {copied
                      ? <span className="text-green-500 text-xs font-medium">Copied</span>
                      : <CopyIcon />
                    }
                  </button>
                </div>
              </div>

              <div className="text-xs text-gray-400 space-y-1">
                <p>Tab didn't open?</p>
                <a
                  href={verificationUri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Open github.com/login/device →
                </a>
              </div>

              <div className="flex items-center justify-center gap-2 text-gray-400">
                <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                <span className="text-xs">Waiting for authorization...</span>
              </div>
            </div>
          )}

          {/* error */}
          {phase === 'error' && (
            <div className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
                {error}
              </div>
              <button
                onClick={retry}
                className="w-full flex items-center justify-center gap-2.5 bg-gray-900 hover:bg-gray-800 text-white py-2.5 px-4 rounded-xl text-sm font-semibold transition-colors"
              >
                <GitHubIcon />
                Try again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
