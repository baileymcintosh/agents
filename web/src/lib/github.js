const OWNER = 'baileymcintosh'
const REPO = 'agents'
const BASE = 'https://api.github.com'
const TOKEN_KEY = 'gh_pat'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/**
 * GitHub Device Flow — works entirely in the browser, no backend needed.
 * The client_id is public (this is by design for device flow apps).
 *
 * Usage:
 *   1. Call startDeviceFlow() → get { device_code, user_code, verification_uri, interval }
 *   2. Show user_code + link to verification_uri
 *   3. Call pollDeviceFlow(device_code, interval) → resolves with access_token
 */

const DEVICE_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID

export async function startDeviceFlow() {
  const res = await fetch('https://github.com/login/device/code', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      client_id: DEVICE_CLIENT_ID,
      scope: 'repo workflow',
    }),
  })
  const data = await res.json()
  if (data.error) throw new Error(data.error_description || data.error)
  return data // { device_code, user_code, verification_uri, expires_in, interval }
}

export async function pollDeviceFlow(deviceCode, intervalSecs = 5) {
  return new Promise((resolve, reject) => {
    const ms = (intervalSecs + 1) * 1000 // add 1s buffer to avoid slow_down errors

    const timer = setInterval(async () => {
      try {
        const res = await fetch('https://github.com/login/oauth/access_token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: JSON.stringify({
            client_id: DEVICE_CLIENT_ID,
            device_code: deviceCode,
            grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          }),
        })
        const data = await res.json()

        if (data.access_token) {
          clearInterval(timer)
          resolve(data.access_token)
        } else if (data.error === 'authorization_pending') {
          // still waiting — keep polling
        } else if (data.error === 'slow_down') {
          // GitHub wants us to back off — handled by the +1s buffer above
        } else if (data.error === 'expired_token') {
          clearInterval(timer)
          reject(new Error('Code expired. Please try again.'))
        } else if (data.error === 'access_denied') {
          clearInterval(timer)
          reject(new Error('Access denied.'))
        }
      } catch (err) {
        clearInterval(timer)
        reject(err)
      }
    }, ms)
  })
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export async function api(path, options = {}) {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.message || `GitHub API error ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export function validateToken() {
  return api('/user')
}

export function dispatchWorkflow(workflowFile, inputs = {}) {
  return api(`/repos/${OWNER}/${REPO}/actions/workflows/${workflowFile}/dispatches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs }),
  })
}

export function listRunsByWorkflow(workflowFile, limit = 10) {
  return api(`/repos/${OWNER}/${REPO}/actions/workflows/${workflowFile}/runs?per_page=${limit}`)
}

export async function listRepos() {
  return api(`/users/${OWNER}/repos?per_page=100&sort=updated&type=public`)
}

export async function readRepoFile(repoName, filePath) {
  try {
    const data = await api(`/repos/${OWNER}/${repoName}/contents/${filePath}`)
    if (data && data.content) {
      return atob(data.content.replace(/\n/g, ''))
    }
    return null
  } catch {
    return null
  }
}

export async function listRuns(limit = 40) {
  return api(`/repos/${OWNER}/${REPO}/actions/runs?per_page=${limit}&exclude_pull_requests=true`)
}

export async function getRun(runId) {
  return api(`/repos/${OWNER}/${REPO}/actions/runs/${runId}`)
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

const _cache = new Map()

export async function cached(key, ttlMs, fn) {
  const hit = _cache.get(key)
  if (hit && Date.now() - hit.ts < ttlMs) return hit.data
  const data = await fn()
  _cache.set(key, { data, ts: Date.now() })
  return data
}

export function clearCache() {
  _cache.clear()
}
