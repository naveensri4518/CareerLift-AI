// CareerLift AI — API client. Talks to the real FastAPI backend.
// No internal implementation details (framework, model, infra) are surfaced to the UI.

// Default to the SAME-ORIGIN "/api" prefix, which the Vite dev server proxies to the backend (see
// vite.config.js). Same-origin requests avoid three local-dev traps at once: the Windows localhost(IPv6
// ::1) vs uvicorn(IPv4 127.0.0.1) mismatch, browser CORS, and a stale VITE_API_BASE pointing at a dead
// port. Set VITE_API_BASE only if you deliberately want to bypass the proxy and hit a backend directly.
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const STORAGE_KEY = 'careerlift.session' // { student_id, token }

export function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveSession(session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY)
}

// A typed error the UI can branch on.
export class ApiError extends Error {
  constructor(status, message, kind) {
    super(message)
    this.status = status
    this.kind = kind // 'network' | 'auth' | 'forbidden' | 'notfound' | 'conflict' | 'badrequest' | 'server'
  }
}

function kindForStatus(status) {
  if (status === 401) return 'auth'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'notfound'
  if (status === 409) return 'conflict'
  if (status === 400 || status === 422) return 'badrequest'
  return 'server'
}

// Friendly, product-level messages — never leak backend internals.
function friendlyMessage(status, detail) {
  switch (status) {
    case 401:
      return 'Your session has expired or is invalid. Please sign in again.'
    case 403:
      return 'You do not have access to this resource.'
    case 404:
      return 'We could not find what you were looking for.'
    case 409:
      return 'This request did not match the active interview. Please start a fresh question.'
    case 400:
    case 422:
      return typeof detail === 'string' ? detail : 'That request was not valid. Please check and try again.'
    default:
      return 'Something went wrong on our side. Please try again in a moment.'
  }
}

async function request(path, { method = 'GET', body, token, signal } = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError(0, 'We could not reach the service. Is it running on your machine?', 'network')
  }

  if (!res.ok) {
    let detail
    try {
      const data = await res.json()
      detail = data?.detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, friendlyMessage(res.status, detail), kindForStatus(res.status))
  }

  if (res.status === 204) return null
  try {
    return await res.json()
  } catch {
    return null
  }
}

// ---- Public API surface (mirrors the backend contract exactly) ----

export const api = {
  health: () => request('/health'),

  // Server GENERATES the id + token. display_name is cosmetic only.
  register: (displayName) =>
    request('/register', { method: 'POST', body: { display_name: displayName || null } }),

  startInterview: (token, { topic, level = 'beginner', role = 'software engineer' }) =>
    request('/interviews', { method: 'POST', token, body: { topic, level, role } }),

  // concept_token is ignored by the server; identity + concepts come from the token + stored interview.
  scoreAnswer: (token, { interviewId, question, answer }) =>
    request('/score', {
      method: 'POST',
      token,
      body: { interview_id: interviewId, question, answer, concept_token: [] },
    }),

  next: (token, studentId) => request(`/students/${encodeURIComponent(studentId)}/next`, { token }),
  history: (token, studentId) => request(`/students/${encodeURIComponent(studentId)}/history`, { token }),
  misconceptions: (token, studentId) =>
    request(`/students/${encodeURIComponent(studentId)}/misconceptions`, { token }),

  // Phase 0 — Learning Intelligence + unified dashboard
  skills: (token, studentId) => request(`/students/${encodeURIComponent(studentId)}/skills`, { token }),
  recommendations: (token, studentId) =>
    request(`/students/${encodeURIComponent(studentId)}/recommendations`, { token }),
  overview: (token, studentId) => request(`/students/${encodeURIComponent(studentId)}/overview`, { token }),
  activity: (token, studentId, days = 90) =>
    request(`/students/${encodeURIComponent(studentId)}/activity?days=${days}`, { token }),

  // Phase 1 — Advanced Interview Studio
  studioCreate: (token, body) => request('/studio/sessions', { method: 'POST', token, body }),
  studioList: (token) => request('/studio/sessions', { token }),
  studioGet: (token, id) => request(`/studio/sessions/${id}`, { token }),
  studioSaveAnswer: (token, id, questionId, answer) =>
    request(`/studio/sessions/${id}/answer`, { method: 'POST', token, body: { question_id: questionId, answer } }),
  studioSubmit: (token, id) => request(`/studio/sessions/${id}/submit`, { method: 'POST', token }),

  // Phase 2 — Secure Coding Arena
  codingProblems: (token) => request('/coding/problems', { token }),
  codingProblem: (token, id) => request(`/coding/problems/${encodeURIComponent(id)}`, { token }),
  codingLanguages: (token) => request('/coding/languages', { token }),
  codingStatus: (token) => request('/coding/status', { token }),
  codingRun: (token, body) => request('/coding/run', { method: 'POST', token, body }),
  codingSubmit: (token, body) => request('/coding/submit', { method: 'POST', token, body }),
  codingSubmissions: (token, problemId) =>
    request(`/coding/submissions${problemId ? `?problem_id=${encodeURIComponent(problemId)}` : ''}`, { token }),

  // Phase 3 — Technical Assessment Engine
  assessmentCatalog: (token) => request('/assessment/catalog', { token }),
  assessmentStart: (token, body) => request('/assessment/attempts', { method: 'POST', token, body }),
  assessmentAttempts: (token) => request('/assessment/attempts', { token }),
  assessmentAttempt: (token, id) => request(`/assessment/attempts/${id}`, { token }),
  assessmentSaveAnswers: (token, id, answers) =>
    request(`/assessment/attempts/${id}/answers`, { method: 'POST', token, body: { answers } }),
  assessmentSubmit: (token, id) => request(`/assessment/attempts/${id}/submit`, { method: 'POST', token }),
  assessmentResult: (token, id) => request(`/assessment/attempts/${id}/result`, { token }),

  // Phase 4 — System Design Academy
  sysdesignScenarios: (token) => request('/sysdesign/scenarios', { token }),
  sysdesignScenario: (token, id) => request(`/sysdesign/scenarios/${encodeURIComponent(id)}`, { token }),
  sysdesignStart: (token, scenarioId) => request('/sysdesign/attempts', { method: 'POST', token, body: { scenario_id: scenarioId } }),
  sysdesignAttempts: (token) => request('/sysdesign/attempts', { token }),
  sysdesignAttempt: (token, id) => request(`/sysdesign/attempts/${id}`, { token }),
  sysdesignSaveDesign: (token, id, design) => request(`/sysdesign/attempts/${id}/design`, { method: 'POST', token, body: design }),
  sysdesignSubmit: (token, id) => request(`/sysdesign/attempts/${id}/submit`, { method: 'POST', token }),
  sysdesignResult: (token, id) => request(`/sysdesign/attempts/${id}/result`, { token }),
}

export { API_BASE }
