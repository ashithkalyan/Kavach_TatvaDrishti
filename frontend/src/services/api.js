import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({ baseURL: BASE, timeout: 30000 })

// Attach the session token to every request automatically once logged in —
// this is what makes the token-based auth real end-to-end, not just a
// login screen that isn't actually wired to anything downstream.
api.interceptors.request.use(config => {
  const token = sessionStorage.getItem('kavach_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// A session that's expired or been revoked comes back as 401 — force a
// clean re-login rather than leaving the UI silently broken.
api.interceptors.response.use(
  res => res,
  err => {
    if (err?.response?.status === 401 && !err.config?.url?.includes('/api/auth/')) {
      sessionStorage.removeItem('kavach_token')
      sessionStorage.removeItem('kavach_user')
      window.location.reload()
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────
export const login = (username, password) =>
  api.post('/api/auth/login', { username, password }).then(r => r.data)

export const register = (username, password, role) =>
  api.post('/api/auth/register', { username, password, role }).then(r => r.data)

export const logout = (token) =>
  api.post('/api/auth/logout', null, { params: { token } }).then(r => r.data)

export const validateSession = (token) =>
  api.get('/api/auth/validate', { params: { token } }).then(r => r.data)

// ── Chat sessions (history sidebar) ──────────────────────────────────────────
// user_id is no longer passed from the client — the backend now derives it
// from the authenticated session token (see main.py's require_auth), which
// is also what fixed history bleeding between different logged-in officers.
export const getChatSessions = () =>
  api.get('/api/chat/sessions').then(r => r.data)

// One combined PDF of chat history — scope: 'login' (everything since this
// sign-in, used automatically right before logout), 'all' (entire history),
// or 'session' (a single conversation, pass sessionId).
export const exportChatHistoryPdf = (scope = 'login', sessionId = null) =>
  api.get('/api/chat/export', {
    params: { scope, ...(sessionId ? { session_id: sessionId } : {}) },
    responseType: 'blob',
  }).then(r => r.data)

// ── Explainability ────────────────────────────────────────────────────────────
export const getIdentityReasoning = (accusedId) =>
  api.get(`/api/accused/${accusedId}/reasoning`).then(r => r.data)

// ── New intelligence endpoints ────────────────────────────────────────────────
export const predictCrime = (district, crimeType, targetMonth, targetYear) =>
  api.get('/api/predict', { params: { district, crime_type: crimeType, target_month: targetMonth, target_year: targetYear } }).then(r => r.data)

// Historical accuracy record for KAVACH's own crime-trend forecasts —
// see backend brain/prediction_tracking.py. Settles any newly-due
// predictions first, then returns the aggregate stats + a recent table.
export const getPredictionAccuracy = (district = null, crimeType = null) =>
  api.get('/api/predict/accuracy', { params: { district, crime_type: crimeType } }).then(r => r.data)

export const findSimilarCases = (firNumber, topK = 5) =>
  api.get(`/api/similarity/${encodeURIComponent(firNumber)}`, { params: { top_k: topK } }).then(r => r.data)

export const getCaseTimeline = (firNumber) =>
  api.get(`/api/timeline/${encodeURIComponent(firNumber)}`).then(r => r.data)

export const getCaseRecommendations = (firNumber) =>
  api.get(`/api/recommendations/${encodeURIComponent(firNumber)}`).then(r => r.data)

// Records whether a recommended lead was useful on a specific case —
// see backend brain/feedback_engine.py. outcome: 'useful' | 'not_useful' | 'inconclusive'.
export const submitLeadFeedback = (firNumber, { lead_key, lead_text, crime_type, outcome, notes }) =>
  api.post(`/api/recommendations/${encodeURIComponent(firNumber)}/feedback`,
    { lead_key, lead_text, crime_type, outcome, notes }).then(r => r.data)

export const getLeadFeedbackSummary = (crimeType = null) =>
  api.get('/api/recommendations/feedback-summary', { params: { crime_type: crimeType } }).then(r => r.data)

// Institutional memory for one case (see backend brain/case_memory.py) —
// case notes + checked-lead history + the investigation-update log,
// assembled into one briefing. Survives an officer transfer by design.
export const getCaseBriefing = (firNumber) =>
  api.get(`/api/cases/${encodeURIComponent(firNumber)}/briefing`).then(r => r.data)

export const listCaseNotes = (firNumber, kind = null) =>
  api.get(`/api/cases/${encodeURIComponent(firNumber)}/notes`, { params: { kind } }).then(r => r.data)

export const addCaseNote = (firNumber, { kind, note_text }) =>
  api.post(`/api/cases/${encodeURIComponent(firNumber)}/notes`, { kind, note_text }).then(r => r.data)

export const resolveCaseNote = (firNumber, noteId, resolved = true) =>
  api.patch(`/api/cases/${encodeURIComponent(firNumber)}/notes/${noteId}/resolve`, null, { params: { resolved } }).then(r => r.data)

// Identity-confidence trajectory (see backend brain/identity_confidence.py)
// — current snapshot + full history, so the UI can show confidence
// actually rising or falling over time, not just today's number.
export const getIdentityConfidenceHistory = (accusedId) =>
  api.get(`/api/accused/${accusedId}/identity-confidence`).then(r => r.data)

export const getIdentitiesNeedingReview = (limit = 50) =>
  api.get('/api/identity/needs-review', { params: { limit } }).then(r => r.data)

export const getCaseSummary = (firNumber) =>
  api.get(`/api/case-summary/${encodeURIComponent(firNumber)}`).then(r => r.data)

export const ingestDocument = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/ingest/document', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

// Writes an investigator-confirmed draft into the live database — the
// second half of ingestion that was previously missing entirely (the
// extraction step above only ever produced a draft that went nowhere).
export const confirmIngest = (payload) =>
  api.post('/api/ingest/confirm', payload).then(r => r.data)

// ── Dashboard ─────────────────────────────────────────────────────────────────
export const getDashboardOverview = () =>
  api.get('/api/dashboard/overview').then(r => r.data)

// ── Chat ──────────────────────────────────────────────────────────────────────
export const sendChatMessage = (message, sessionId, language = 'en') =>
  api.post('/api/chat', { message, session_id: sessionId, language }).then(r => r.data)

export const getChatHistory = sessionId =>
  api.get(`/api/chat/history/${sessionId}`).then(r => r.data)

export const clearChatHistory = sessionId =>
  api.delete(`/api/chat/history/${sessionId}`).then(r => r.data)

// Live, token-by-token counterpart to sendChatMessage() — same brain
// pipeline, same grounding guarantees (see backend main.py's POST
// /api/chat/stream docstring), but the reply arrives as a Server-Sent
// Events stream instead of one blocking response. Uses raw fetch()
// rather than the axios instance above because axios doesn't expose a
// readable stream of the response body; the auth token is attached by
// hand below to match what the axios interceptor does automatically.
//
// handlers:
//   onMeta(data)     — sent once, near the start: intent/sql/results/etc.
//   onToken(text)    — a piece of provisional reply text, called repeatedly
//   onConfirm()      — every token sent so far is final (grounding passed)
//   onRetract()      — discard every token sent so far (grounding failed;
//                      a corrected reply will arrive via onToken again,
//                      then onDone)
//   onDone(data)     — sent once, at the very end: final text + response_source
//                      + notable_insight + timestamp
//   onError(message) — something went wrong; treat like a failed request
// `signal` (optional) — an AbortSignal to cancel the stream early.
export async function streamChatMessage(message, sessionId, language = 'en', handlers = {}) {
  const { onMeta, onToken, onConfirm, onRetract, onDone, onError, signal } = handlers
  const token = sessionStorage.getItem('kavach_token')

  const resp = await fetch(`${BASE}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId, language }),
    signal,
  })

  if (resp.status === 401) {
    sessionStorage.removeItem('kavach_token')
    sessionStorage.removeItem('kavach_user')
    window.location.reload()
    return
  }
  if (!resp.ok || !resp.body) {
    const text = await resp.text().catch(() => '')
    throw new Error(`Stream request failed (${resp.status}): ${text || resp.statusText}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let frameEnd
    while ((frameEnd = buffer.indexOf('\n\n')) !== -1) {
      const frame = buffer.slice(0, frameEnd)
      buffer = buffer.slice(frameEnd + 2)

      let eventType = 'message'
      const dataLines = []
      for (const line of frame.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue

      let data
      try {
        data = JSON.parse(dataLines.join('\n'))
      } catch {
        continue // malformed frame — skip rather than crash the stream
      }

      switch (eventType) {
        case 'meta': onMeta && onMeta(data); break
        case 'token': onToken && onToken(data.text || ''); break
        case 'confirm': onConfirm && onConfirm(); break
        case 'retract': onRetract && onRetract(); break
        case 'done': onDone && onDone(data); break
        case 'error': onError && onError(data.message || 'Stream error'); break
        default: break
      }
    }
  }
}

// ── Chat with a PDF ──────────────────────────────────────────────────────────
// Uploads a PDF/photo as SCRATCH CONTEXT for one chat session — never the
// case database. See backend brain/document_context.py's module docstring.
export const uploadChatDocument = (file, sessionId) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/api/chat/upload-document', formData, {
    params: { session_id: sessionId },
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)
}

export const clearChatDocument = sessionId =>
  api.delete(`/api/chat/document/${sessionId}`).then(r => r.data)

// Read-only lookup used to restore the "document attached" chip when a
// past session is reopened — {attached: false} or {attached: true,
// filename, char_count, save_result}.
export const getChatDocument = sessionId =>
  api.get(`/api/chat/document/${sessionId}`).then(r => r.data)

// Records that this session's document was successfully confirmed into
// a real case, so the "Saved — FIR ... is now live" confirmation
// survives a reload or switching sessions and back — see
// DocumentReviewCard.jsx. Called right after confirmIngest() succeeds;
// best-effort (the save itself already happened either way).
export const saveChatDocumentResult = (sessionId, saveResult) =>
  api.post(`/api/chat/document/${sessionId}/save-result`, { save_result: saveResult }).then(r => r.data)

// ── FIR ───────────────────────────────────────────────────────────────────────
export const searchFIRs = params =>
  api.get('/api/fir', { params }).then(r => r.data)

export const getFIRDetail = firNumber =>
  api.get(`/api/fir/${encodeURIComponent(firNumber)}`).then(r => r.data)

// ── Accused ───────────────────────────────────────────────────────────────────
export const searchAccused = params =>
  api.get('/api/accused', { params }).then(r => r.data)

export const getAccusedProfile = id =>
  api.get(`/api/accused/${id}`).then(r => r.data)

export const getAccusedNetwork = (id, depth = 2) =>
  api.get(`/api/accused/${id}/network`, { params: { depth } }).then(r => r.data)

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getCrimeTrends = params =>
  api.get('/api/analytics/trends', { params }).then(r => r.data)

export const getHotspots = params =>
  api.get('/api/analytics/hotspots', { params }).then(r => r.data)

export const getDemographics = () =>
  api.get('/api/analytics/demographics').then(r => r.data)

export const getDistrictSummary = () =>
  api.get('/api/analytics/district-summary').then(r => r.data)

// ── Network Graph ─────────────────────────────────────────────────────────────
export const getFullNetworkGraph = (limit = 80) =>
  api.get('/api/network/graph', { params: { limit } }).then(r => r.data)

export const getGangs = () =>
  api.get('/api/network/gangs').then(r => r.data)

// ── Translation ───────────────────────────────────────────────────────────────
export const translateText = (text, targetLanguage = 'kn') =>
  api.post('/api/translate', { text, target_language: targetLanguage }).then(r => r.data)

// ── Meta ─────────────────────────────────────────────────────────────────────
export const getDistricts = () =>
  api.get('/api/meta/districts').then(r => r.data)

export const getCrimeTypes = () =>
  api.get('/api/meta/crime-types').then(r => r.data)

// With real IDs (unlike getCrimeTypes above, which is name-only and used
// for chat-query filtering) — needed to commit a confirmed ingestion draft.
export const getPoliceStations = (district = null) =>
  api.get('/api/meta/police-stations', { params: district ? { district } : {} }).then(r => r.data)

export const getCrimeSubheads = () =>
  api.get('/api/meta/crime-subheads').then(r => r.data)

export const getCaseStatuses = () =>
  api.get('/api/meta/case-statuses').then(r => r.data)

export const healthCheck = () =>
  api.get('/api/health').then(r => r.data)

// ── Hotspot forecast / NCRB benchmark / audit log ───────────────────────────────
export const getHotspotForecast = (topN = 15) =>
  api.get('/api/analytics/hotspot-forecast', { params: { top_n: topN } }).then(r => r.data)

export const getNcrbBenchmark = () =>
  api.get('/api/analytics/ncrb-benchmark').then(r => r.data)

export const getAuditLog = (limit = 200, userIdFilter = null) =>
  api.get('/api/admin/audit-log', { params: userIdFilter ? { limit, user_id_filter: userIdFilter } : { limit } })
    .then(r => r.data)
