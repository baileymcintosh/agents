const OWNER = 'baileymcintosh'
const REPO = 'agents'
const BASE = 'https://api.github.com'
const TOKEN_KEY = 'gh_pat'

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

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
  // 204 No Content
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

export function listRuns(limit = 30) {
  return api(`/repos/${OWNER}/${REPO}/actions/runs?per_page=${limit}&exclude_pull_requests=true`)
}

export function listRunsByWorkflow(workflowFile, limit = 10) {
  return api(`/repos/${OWNER}/${REPO}/actions/workflows/${workflowFile}/runs?per_page=${limit}`)
}
