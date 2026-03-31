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
 * Exchange a GitHub OAuth code for an access token via the Netlify function.
 * The function keeps the client_secret server-side.
 */
export async function exchangeOAuthCode(code) {
  const res = await fetch('/.netlify/functions/github-oauth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  const data = await res.json()
  if (!res.ok || data.error) throw new Error(data.error || 'OAuth exchange failed')
  return data.access_token
}

/**
 * Redirect to GitHub OAuth authorization page.
 * scope=repo gives read access; workflow adds dispatch access.
 */
export function redirectToGitHubOAuth() {
  const clientId = import.meta.env.VITE_GITHUB_CLIENT_ID
  if (!clientId) {
    alert('VITE_GITHUB_CLIENT_ID is not set. Check Netlify env vars and rebuild.')
    return
  }
  const params = new URLSearchParams({
    client_id: clientId,
    scope: 'repo workflow',
    redirect_uri: window.location.origin + '/',
  })
  window.location.href = `https://github.com/login/oauth/authorize?${params}`
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

// List all repos for the owner
export async function listRepos() {
  return api(`/users/${OWNER}/repos?per_page=100&sort=updated&type=public`)
}

// Read a file from a project repo. Returns decoded text or null.
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

// List workflow runs for the agents repo
export async function listRuns(limit = 40) {
  return api(`/repos/${OWNER}/${REPO}/actions/runs?per_page=${limit}&exclude_pull_requests=true`)
}

// Get a single workflow run
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
