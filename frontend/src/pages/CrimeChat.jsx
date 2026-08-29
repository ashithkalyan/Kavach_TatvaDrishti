import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send, Mic, MicOff, FileDown, Trash2,
  ChevronDown, ChevronRight, AlertCircle, Zap, HelpCircle,
  Network as NetIcon, User, History, Plus, MessageSquare, ShieldCheck,
  Paperclip, X, FileText,
} from 'lucide-react'
import {
  streamChatMessage, getChatHistory, getChatSessions, exportChatHistoryPdf,
  uploadChatDocument, clearChatDocument, getChatDocument,
} from '../services/api'
import Header from '../components/Header'
import MiniNetworkGraph from '../components/MiniNetworkGraph'
import DocumentReviewCard from '../components/DocumentReviewCard'
import { useLanguage } from '../i18n/LanguageContext'

const STARTERS = {
  en: [
    'Show me repeat offenders in Bengaluru with 3+ convictions',
    'List all murder cases in Mysuru from 2023 onwards',
    'Which police station has the highest theft cases?',
    'Show high-risk accused in the Hubballi Drug Syndicate',
    'Find all cybercrime cases with property value above 1 lakh',
    'Show gang-affiliated accused with EXTREME risk score',
  ],
  kn: [
    'ಬೆಂಗಳೂರಿನಲ್ಲಿ 3+ ಶಿಕ್ಷೆಗಳೊಂದಿಗೆ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳನ್ನು ತೋರಿಸಿ',
    '2023 ರಿಂದ ಮೈಸೂರಿನಲ್ಲಿ ಎಲ್ಲಾ ಕೊಲೆ ಪ್ರಕರಣಗಳನ್ನು ಪಟ್ಟಿ ಮಾಡಿ',
    'ಯಾವ ಪೊಲೀಸ್ ಠಾಣೆಯಲ್ಲಿ ಅತಿ ಹೆಚ್ಚು ಕಳ್ಳತನ ಪ್ರಕರಣಗಳಿವೆ?',
    'ಗ್ಯಾಂಗ್ ಸಂಬಂಧಿತ ಆರೋಪಿಗಳನ್ನು EXTREME ಅಪಾಯದ ಅಂಕದೊಂದಿಗೆ ತೋರಿಸಿ',
  ],
}

const RISK_COLORS = { EXTREME: '#C0392B', HIGH: '#E67E22', MEDIUM: '#F39C12', LOW: '#0F7A5A' }

function RiskBadge({ risk }) {
  return (
    <span className={`risk-badge risk-${risk}`}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: RISK_COLORS[risk], flexShrink: 0 }} />
      {risk}
    </span>
  )
}

function ResultCard({ row, onViewNetwork, onViewProfile }) {
  if (row.accused_id) return (
    <div style={{
      background: '#fff', border: '1px solid #E2E8F0', borderRadius: 6,
      padding: '10px 12px', animation: 'fadeIn 0.25s ease-out',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E293B' }}>{row.name}</div>
        {row.risk_category && <RiskBadge risk={row.risk_category} />}
      </div>
      <div style={{ fontSize: '0.68rem', color: '#64748B', lineHeight: 1.6 }}>
        {row.age && <span>Age: {row.age} • </span>}
        {row.gender && <span>{row.gender} • </span>}
        {row.district && <span>{row.district}</span>}
        {row.prior_convictions > 0 && <div style={{ color: '#C0392B', fontWeight: 600, marginTop: 3 }}>⚠ {row.prior_convictions} prior conviction(s)</div>}
        {row.gang_affiliation && <div style={{ color: '#7E22CE', marginTop: 2 }}>🔗 {row.gang_affiliation}</div>}
        {row.modus_operandi && <div style={{ color: '#475569', marginTop: 3, fontSize: '0.65rem', fontStyle: 'italic' }}>MO: {row.modus_operandi?.slice(0,60)}…</div>}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <button onClick={() => onViewProfile(row.accused_id)} style={{ fontSize: '0.65rem', padding: '3px 8px', border: '1px solid #E2E8F0', borderRadius: 4, background: '#F8FAFC', cursor: 'pointer', color: '#475569', display: 'flex', alignItems: 'center', gap: 4 }}>
          <User size={10} />Profile
        </button>
        <button onClick={() => onViewNetwork(row.accused_id)} style={{ fontSize: '0.65rem', padding: '3px 8px', border: '1px solid #BFDBFE', borderRadius: 4, background: '#EFF6FF', cursor: 'pointer', color: '#1D4ED8', display: 'flex', alignItems: 'center', gap: 4 }}>
          <NetIcon size={10} />Network
        </button>
      </div>
    </div>
  )

  if (row.fir_number) return (
    <div style={{
      background: '#fff', border: '1px solid #E2E8F0', borderRadius: 6,
      padding: '10px 12px', animation: 'fadeIn 0.25s ease-out',
    }}>
      <div style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: '#1D4ED8', fontWeight: 700, marginBottom: 4 }}>
        {row.fir_number}
      </div>
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#1E293B', marginBottom: 4 }}>{row.crime_type || row.crime_description?.slice(0,50)}</div>
      <div style={{ fontSize: '0.68rem', color: '#64748B', lineHeight: 1.5 }}>
        {row.district && <span>{row.district}</span>}
        {row.police_station && <span> • {row.police_station}</span>}
        {row.registration_date && <span> • {row.registration_date}</span>}
        {row.property_value > 0 && <div style={{ marginTop: 2 }}>₹{row.property_value?.toLocaleString('en-IN')}</div>}
      </div>
      {row.status && (
        <div style={{ marginTop: 6 }}>
          <span className={`status-pill ${
            row.status === 'Under Investigation' ? 'status-open' :
            row.status === 'Charge-Sheeted' ? 'status-sheeted' :
            row.status === 'Closed' ? 'status-closed' : 'status-filed'
          }`}>{row.status}</span>
        </div>
      )}
    </div>
  )

  // Generic row
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 6, padding: '8px 10px', fontSize: '0.72rem', color: '#334155', animation: 'fadeIn 0.2s ease-out' }}>
      {Object.entries(row).slice(0, 5).map(([k, v]) => v && (
        <div key={k} style={{ display: 'flex', gap: 6, marginBottom: 2 }}>
          <span style={{ color: '#94A3B8', minWidth: 80, flexShrink: 0 }}>{k.replace(/_/g,' ')}:</span>
          <span style={{ fontWeight: 500 }}>{String(v).slice(0, 60)}</span>
        </div>
      ))}
    </div>
  )
}

function speakingKey(msg, idx) { return `${idx}-${msg.timestamp || ''}` }

function AIMessage({ msg, idx, onViewNetwork, onViewProfile, onSuggestionClick, t,
                     speakingId, onToggleSpeak, sessionId }) {
  const [showReasoning, setShowReasoning] = useState(false)
  const isClarification = !!msg.needs_clarification
  const isSpeaking = speakingId === speakingKey(msg, idx)
  const hasReasoning = !!(msg.sql_generated || msg.pipeline_trace?.length > 0 || msg.alias_matches?.length > 0)

  // Resolver-tier summary — the top alias match, always shown (not just
  // non-exact matches) since "which tier matched, with its confidence"
  // is exactly what the Reasoning panel promises to show.
  const topMatch = msg.alias_matches?.[0]
  const tierLabels = { exact: 'Exact match', alias: 'Alias dictionary', phonetic: 'Phonetic match', fuzzy: 'Fuzzy match' }

  const groundedBadge = {
    ollama_grounded: { label: '✓ Grounded by Ollama', color: '#0F7A5A', bg: '#F0FDF4', border: '#BBF7D0' },
    ollama_polish: { label: '✎ Polished by Ollama (facts from template)', color: '#B45309', bg: '#FFFBEB', border: '#FDE68A' },
    general_knowledge: { label: '📖 Curated reference — not case data', color: '#6B21A8', bg: '#FAF5FF', border: '#E9D5FF' },
    document_grounded: { label: '📄 Grounded in attached document — not the case database', color: '#0F7A5A', bg: '#F0FDF4', border: '#BBF7D0' },
    template: { label: 'Deterministic template (no LLM used)', color: '#475569', bg: '#F8FAFC', border: '#E2E8F0' },
  }[msg.response_source] || null

  // Live-streaming display state (see streamChatMessage() in
  // services/api.js and CrimeChat.jsx's send()): show typing dots until
  // the first token of THIS reply has actually arrived, then the text
  // itself with a blinking cursor until the 'done' event lands.
  const isStreaming = !!msg.streaming
  const showDots = isStreaming && !msg.interpretation

  return (
    <div className="msg-row">
      <div className="msg-avatar avatar-ai" style={isClarification ? { background: '#7E22CE' } : undefined}>
        {isClarification ? '?' : 'AI'}
      </div>
      <div style={{ flex: 1, maxWidth: '72%' }}>
        <div
          className="msg-bubble bubble-ai"
          style={isClarification ? { background: '#FAF5FF', border: '1px solid #E9D5FF' } : undefined}
        >
          {/* Memory recall banner */}
          {msg.memory_recalled && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 6,
              background: '#F5F3FF', border: '1px solid #E9D5FF',
              borderRadius: 5, padding: '6px 10px', marginBottom: 8,
              fontSize: '0.7rem', color: '#6B21A8',
            }}>
              <span>🧠</span>
              <span>Recalled from your {msg.memory_recalled.date} session: "{msg.memory_recalled.text}"</span>
            </div>
          )}

          {/* Intent label (or a "needs clarification" label instead) */}
          {isClarification ? (
            <div style={{ fontSize: '0.65rem', color: '#7E22CE', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
              <HelpCircle size={11} color="#7E22CE" />
              {t('chatClarifying')}
            </div>
          ) : msg.intent && (
            <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Zap size={10} color="#C5A028" />
              {msg.intent}
            </div>
          )}

          {/* Interpretation — typing dots until the first token of this
              reply arrives, then live text with a blinking cursor until
              the stream's 'done' event lands (see msg.streaming). */}
          {showDots ? (
            <div className="typing-dots">
              <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
            </div>
          ) : (
            <div style={{ fontSize: '0.82rem', lineHeight: 1.65, color: '#1E293B', whiteSpace: 'pre-wrap' }}>
              {msg.interpretation}
              {isStreaming && <span className="streaming-cursor" />}
            </div>
          )}

          {/* Small inline network snapshot — only present when the brain
              actually found a connected network worth showing; a static
              glance-visual, not the full interactive Network page. */}
          {msg.network_snapshot && <MiniNetworkGraph snapshot={msg.network_snapshot} />}

          {/* Insights */}
          {msg.insights && msg.insights !== msg.interpretation && (
            <div style={{
              marginTop: 10, padding: '8px 10px',
              background: '#FFFBEB', border: '1px solid #FDE68A',
              borderRadius: 5, fontSize: '0.72rem', color: '#78350F',
            }}>
              <strong>📊 Insight:</strong> {msg.insights}
            </div>
          )}

          {/* Self-critique note — a short, already grounding-checked
              observation the model surfaced alongside its reply, only
              when it clears a real bar (see backend
              ollama_client._clears_notable_bar()). Usually absent, which
              is expected, not a failure. */}
          {msg.notable_insight && (
            <div style={{
              marginTop: 8, padding: '8px 10px',
              background: '#F5F3FF', border: '1px solid #DDD6FE',
              borderRadius: 5, fontSize: '0.72rem', color: '#4C1D95',
            }}>
              <strong>🧭 Worth noting:</strong> {msg.notable_insight}
            </div>
          )}

          {/* Chat-with-a-PDF review draft — rendered inline, never a
              redirect to another page. Nothing here has been saved to
              the case database yet; see DocumentReviewCard.jsx. */}
          {msg.document_draft && (
            <DocumentReviewCard draft={msg.document_draft} filename={msg.document_attached?.filename || 'document'}
              sessionId={sessionId} initialSaveResult={msg.document_save_result || null} />
          )}

          {/* Result count — plain-language, points the officer at the
              panel rather than a bare "N records found" line — and never
              rendered for clarification turns, since those never carry
              results by design (see brain.py). */}
          {msg.result_count > 0 && (
            <div style={{ marginTop: 8, fontSize: '0.68rem', color: '#64748B' }}>
              I've found {msg.result_count} matching record{msg.result_count !== 1 ? 's' : ''} — see {msg.result_count > 1 ? 'them' : 'it'} in the panel on the right
              {msg.result_count > 10 && ' (showing the top 10 there)'}.
            </div>
          )}

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4, alignItems: 'center' }}>
            {/* Unified Reasoning panel — resolver tier, generated SQL, and
                whether/how Ollama touched the phrasing, all in one place,
                so the deterministic-pipeline story is a demo moment
                instead of a paragraph in a doc. */}
            {hasReasoning && (
              <button className="sql-pill" onClick={() => setShowReasoning(!showReasoning)}>
                <span style={{ color: '#7E22CE' }}>🧠</span>
                Reasoning
                {showReasoning ? <ChevronDown size={10}/> : <ChevronRight size={10}/>}
              </button>
            )}
            {msg.identity_reasoning_trace && (
              <span style={{ fontSize: '0.65rem', color: '#0F7A5A', display: 'flex', alignItems: 'center', gap: 4 }}>
                <ShieldCheck size={11} color="#0F7A5A" />
                {msg.identity_reasoning_trace.confidence_pct}
              </span>
            )}
            {/* Read-aloud — on demand only, not automatic (an officer in
                the field shouldn't have every reply narrated whether they
                want it or not). Hidden while the reply is still streaming
                in, since reading out a partial sentence isn't useful. */}
            {!isStreaming && msg.interpretation && !!window.speechSynthesis && (
              <button
                onClick={() => onToggleSpeak(msg, idx)}
                title={isSpeaking ? 'Stop reading aloud' : 'Read this reply aloud'}
                className="sql-pill"
                style={isSpeaking ? { background: '#0B1D3A', color: '#C5A028', borderColor: '#0B1D3A' } : undefined}
              >
                {isSpeaking ? '■ Stop' : '🔊 Listen'}
              </button>
            )}
          </div>

          {showReasoning && (
            <div style={{
              marginTop: 6, background: '#FAF5FF', border: '1px solid #E9D5FF',
              borderRadius: 4, padding: '8px 10px', fontSize: '0.68rem', color: '#581C87',
            }}>
              {groundedBadge && (
                <div style={{
                  display: 'inline-block', marginBottom: 8, padding: '3px 8px', borderRadius: 4,
                  fontSize: '0.65rem', fontWeight: 700,
                  color: groundedBadge.color, background: groundedBadge.bg, border: `1px solid ${groundedBadge.border}`,
                }}>
                  {groundedBadge.label}
                </div>
              )}
              {topMatch && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontWeight: 700, marginBottom: 2 }}>Name resolution</div>
                  <div>
                    {topMatch.name} — <strong>{tierLabels[topMatch.method] || topMatch.method}</strong>{' '}
                    ({Math.round(topMatch.confidence * 100)}% confidence)
                  </div>
                </div>
              )}
              {msg.sql_generated && (
                <div style={{ marginBottom: 8 }}>
                  <div style={{ fontWeight: 700, marginBottom: 2 }}>Generated SQL</div>
                  <div className="sql-code" style={{ marginTop: 0 }}>{msg.sql_generated}</div>
                </div>
              )}
              {msg.pipeline_trace?.length > 0 && (
                <div>
                  <div style={{ fontWeight: 700, marginBottom: 2 }}>Pipeline trace</div>
                  {msg.pipeline_trace.map((step, i) => (
                    <div key={i} style={{ marginBottom: 3, display: 'flex', gap: 6 }}>
                      <span style={{ color: '#A855F7', flexShrink: 0 }}>{i + 1}.</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}
              {msg.identity_reasoning_trace && (
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #E9D5FF' }}>
                  <div style={{ fontWeight: 700, marginBottom: 2, color: '#14532D' }}>
                    Identity confidence — {msg.identity_reasoning_trace.confidence_pct}
                  </div>
                  <div style={{ color: '#14532D' }}>
                    {msg.identity_reasoning_trace.officer_summary || msg.identity_reasoning_trace.conclusion}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Follow-up suggestions */}
        {msg.follow_up_suggestions?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
            {msg.follow_up_suggestions.map((s, i) => (
              <button key={i} className="suggestion-chip" onClick={() => onSuggestionClick(s)}>
                <ChevronRight size={10} />
                {s}
              </button>
            ))}
          </div>
        )}

        <div style={{ fontSize: '0.6rem', color: '#CBD5E1', marginTop: 5 }}>{msg.timestamp}</div>
      </div>
    </div>
  )
}

function UserMessage({ text, time }) {
  return (
    <div className="msg-row user">
      <div className="msg-avatar avatar-user">YOU</div>
      <div>
        <div className="msg-bubble bubble-user">{text}</div>
        <div style={{ fontSize: '0.6rem', color: '#CBD5E1', marginTop: 4, textAlign: 'right' }}>{time}</div>
      </div>
    </div>
  )
}

export default function CrimeChat({ user }) {
  const { language, t } = useLanguage()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [recording, setRecording] = useState(false)
  const [micNotice, setMicNotice] = useState(null)
  const [panelResults, setPanelResults] = useState([])
  const [panelTitle, setPanelTitle] = useState('Query Results')
  const [showHistory, setShowHistory] = useState(true)
  const [pastSessions, setPastSessions] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState(false)
  const [speakingId, setSpeakingId] = useState(null)
  const [restoring, setRestoring] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [attachedDoc, setAttachedDoc] = useState(null)   // {filename, char_count} | null
  const [uploadingDoc, setUploadingDoc] = useState(false)
  const [docNotice, setDocNotice] = useState(null)       // {type: 'success'|'error', text}
  const messagesEndRef = useRef(null)
  const recognitionRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const welcomeMessage = useCallback(() => ({
    type: 'ai',
    interpretation: language === 'kn'
      ? `ನಮಸ್ಕಾರ ${user?.full_name?.split(' ')[1] || 'ಅಧಿಕಾರಿ'}. ನಾನು ಕವಚ-AI, ನಿಮ್ಮ ಬುದ್ಧಿವಂತ ಅಪರಾಧ ವಿಶ್ಲೇಷಣಾ ಸಹಾಯಕ.\n\nFIR ದಾಖಲೆಗಳು, ಆರೋಪಿಗಳ ಪ್ರೊಫೈಲ್‌ಗಳು, ಅಪರಾಧ ಪ್ರವೃತ್ತಿಗಳು, ಗ್ಯಾಂಗ್ ಜಾಲಗಳು ಅಥವಾ ಪುನರಾವರ್ತಿತ ಅಪರಾಧಿಗಳ ಬಗ್ಗೆ ನೀವು ಸಹಜ ಭಾಷೆಯಲ್ಲಿ ಏನನ್ನಾದರೂ ಕೇಳಬಹುದು.`
      : `Namaskara ${user?.full_name?.split(' ')[1] || 'Officer'}. I am KAVACH-AI, your intelligent crime analytics assistant.\n\nYou can ask me anything about FIR records, accused profiles, crime trends, gang networks, or repeat offenders — in natural language. Try a query below or use your voice.`,
    intent: 'Welcome', sql_generated: null, insights: null,
    follow_up_suggestions: STARTERS[language].slice(0, 3), result_count: 0,
    timestamp: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
    results: [],
  }), [user, language])

  // Restore the last active session on mount — fixes losing the whole
  // conversation on every page refresh. sessionStorage (not localStorage)
  // deliberately: a shared/kiosk machine shouldn't keep another officer's
  // conversation alive after the browser tab closes — and App.jsx clears
  // this key on every fresh login, so signing out and back in always
  // starts a clean conversation too.
  useEffect(() => {
    const savedId = sessionStorage.getItem('kavach_active_chat_session')
    if (savedId) {
      loadSession(savedId).finally(() => setRestoring(false))
    } else {
      setMessages([welcomeMessage()])
      setRestoring(false)
    }
    // Prefetch the history rail's contents on page load — previously this
    // only ever fetched when the officer clicked the History button, so a
    // slow or failed request looked identical to "no past conversations",
    // which is one plausible read of "the past chats don't show". Shown
    // by default now (ChatGPT-style persistent rail) rather than hidden
    // behind a click.
    loadSessionsList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadSession(sid) {
    try {
      const data = await getChatHistory(sid)
      if (!data.history || data.history.length === 0) {
        setMessages([welcomeMessage()])
        setSessionId(null)
        setAttachedDoc(null)
        sessionStorage.removeItem('kavach_active_chat_session')
        return
      }
      const rehydrated = data.history.map(turn => {
        const time = turn.timestamp
          ? new Date(turn.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
          : ''
        if (turn.role === 'user') {
          return { type: 'user', text: turn.text, time }
        }
        // Prefer the fully-persisted turn (reasoning trace, network
        // snapshot, results, document draft — everything, see
        // memory_engine.store_turn()'s full_response_json). This is
        // what keeps the Reasoning button, the network tab, and the
        // document review card intact when switching chat sessions and
        // back — previously only the bare reply text was ever stored,
        // so all of that vanished on reload (a reported bug). Falls
        // back to bare-text display for any turn stored before this
        // existed, so old sessions still open, just with less detail.
        if (turn.full_response) {
          return { type: 'ai', ...turn.full_response, timestamp: time }
        }
        return { type: 'ai', interpretation: turn.text, intent: '', sql_generated: null,
                 insights: null, notable_insight: null, follow_up_suggestions: [], result_count: 0,
                 results: [], document_attached: null, document_draft: null, timestamp: time }
      })
      setMessages(rehydrated)
      setSessionId(sid)
      sessionStorage.setItem('kavach_active_chat_session', sid)
      // Best-effort restore of the "document attached" chip AND, if the
      // officer already confirmed a save earlier in this session, the
      // review card's "Saved" state too (see document_context.py's
      // save_result_json) — without this, reopening a session where a
      // case was already saved would show the blank edit form again
      // instead of the "Saved — FIR ... is now live" confirmation
      // (another reported bug).
      getChatDocument(sid)
        .then(doc => {
          setAttachedDoc(doc.attached ? { filename: doc.filename, char_count: doc.char_count } : null)
          if (doc.attached && doc.save_result) {
            setMessages(prev => {
              const lastDraftIdx = [...prev].map(m => !!m.document_draft).lastIndexOf(true)
              if (lastDraftIdx === -1) return prev
              const next = [...prev]
              next[lastDraftIdx] = { ...next[lastDraftIdx], document_save_result: doc.save_result }
              return next
            })
          }
        })
        .catch(() => {})
    } catch {
      setMessages([welcomeMessage()])
    }
  }

  async function loadSessionsList() {
    setHistoryLoading(true)
    setHistoryError(false)
    try {
      const data = await getChatSessions()
      setPastSessions(data.sessions || [])
    } catch {
      // Previously swallowed silently with no loading/error state at all —
      // which meant a slow or failed request rendered identically to
      // "you have no past conversations", indistinguishable from a real
      // empty state. Now surfaced honestly with a retry.
      setHistoryError(true)
    } finally {
      setHistoryLoading(false)
    }
  }

  function startNewSession() {
    setMessages([welcomeMessage()])
    setSessionId(null)
    setPanelResults([])
    setAttachedDoc(null)
    setDocNotice(null)
    sessionStorage.removeItem('kavach_active_chat_session')
  }

  // On-demand read-aloud — replaces the old "speak every response
  // automatically" behaviour. An officer in the field should get to
  // choose when a reply is read aloud, not have every reply narrated
  // whether they want it or not.
  function toggleSpeak(msg, idx) {
    const key = speakingKey(msg, idx)
    if (speakingId === key) {
      window.speechSynthesis.cancel()
      setSpeakingId(null)
      return
    }
    window.speechSynthesis.cancel() // stop whatever else might be playing
    const utt = new SpeechSynthesisUtterance(msg.interpretation)
    utt.lang = language === 'kn' ? 'kn-IN' : 'en-IN'
    utt.onend = () => setSpeakingId(null)
    utt.onerror = () => setSpeakingId(null)
    window.speechSynthesis.speak(utt)
    setSpeakingId(key)
  }

  // Generates a session id client-side (same "sess_" + 8 hex chars shape
  // main.py uses server-side) so a document can be attached BEFORE the
  // very first chat message is sent — otherwise there'd be no session_id
  // yet for the upload to attach to. If a message has already been sent,
  // the real server-assigned session_id is reused instead.
  function ensureSessionId() {
    if (sessionId) return sessionId
    const bytes = crypto.getRandomValues(new Uint8Array(4))
    const newId = `sess_${Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')}`
    setSessionId(newId)
    sessionStorage.setItem('kavach_active_chat_session', newId)
    return newId
  }

  async function handleAttachDocument(file) {
    if (!file) return
    const okTypes = ['application/pdf', 'image/png', 'image/jpeg']
    const okExt = /\.(pdf|png|jpe?g)$/i.test(file.name)
    if (!okTypes.includes(file.type) && !okExt) {
      setDocNotice({ type: 'error', text: 'Only PDF, PNG, or JPG files are supported.' })
      return
    }
    const sid = ensureSessionId()
    setUploadingDoc(true)
    setDocNotice(null)
    try {
      const data = await uploadChatDocument(file, sid)
      setAttachedDoc({ filename: data.filename, char_count: data.char_count })
      setDocNotice({
        type: 'success',
        text: `${data.filename} attached — ${data.char_count.toLocaleString('en-IN')} characters extracted. Ask about it, or say "extract this into a case".`,
      })
    } catch (err) {
      setDocNotice({ type: 'error', text: err?.response?.data?.detail || 'Could not extract text from this file.' })
    } finally {
      setUploadingDoc(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleDetachDocument() {
    const sid = sessionId
    setAttachedDoc(null)
    setDocNotice(null)
    if (sid) {
      try { await clearChatDocument(sid) } catch { /* best-effort */ }
    }
  }

  const send = useCallback(async (text = input.trim()) => {
    if (!text || loading) return
    setInput('')
    setMicNotice(null)
    const userTime = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    const activeSessionId = sessionId || (attachedDoc ? ensureSessionId() : sessionId)

    setMessages(prev => [...prev, { type: 'user', text, time: userTime }])
    setLoading(true)

    // Live placeholder message, filled in progressively as SSE events
    // arrive and finalized on 'done' — see streamChatMessage() in
    // services/api.js and backend main.py's POST /api/chat/stream. Track
    // its index via a ref-like holder since state updates are async and
    // we need the SAME index for every later patch in this turn.
    const holder = { idx: null }
    setMessages(prev => {
      holder.idx = prev.length
      return [...prev, {
        type: 'ai', streaming: true, interpretation: '', intent: null,
        sql_generated: null, insights: null, notable_insight: null,
        follow_up_suggestions: [], result_count: 0, results: [],
        document_attached: null, document_draft: null,
        timestamp: userTime,
      }]
    })

    const patch = (fields) => {
      setMessages(prev => {
        if (holder.idx == null || !prev[holder.idx]) return prev
        const next = [...prev]
        next[holder.idx] = { ...next[holder.idx], ...fields }
        return next
      })
    }

    let accumulated = ''

    try {
      await streamChatMessage(text, activeSessionId, language, {
        onMeta: (data) => {
          if (!sessionId && data.session_id) {
            setSessionId(data.session_id)
            sessionStorage.setItem('kavach_active_chat_session', data.session_id)
          }
          patch({
            intent: data.intent, sql_generated: data.sql_generated, insights: data.insights,
            follow_up_suggestions: data.follow_up_suggestions, result_count: data.result_count,
            results: data.results, alias_matches: data.alias_matches, memory_recalled: data.memory_recalled,
            pipeline_trace: data.pipeline_trace, routed_engine: data.routed_engine,
            identity_reasoning_trace: data.identity_reasoning_trace,
            needs_clarification: data.needs_clarification, network_snapshot: data.network_snapshot,
            document_attached: data.document_attached, document_draft: data.document_draft,
          })
          if (data.results?.length > 0) {
            setPanelResults(data.results.slice(0, 15))
            setPanelTitle(`${data.result_count} Result${data.result_count !== 1 ? 's' : ''} — ${data.intent || 'Query'}`)
          }
        },
        onToken: (chunk) => {
          accumulated += chunk
          patch({ interpretation: accumulated })
        },
        onRetract: () => {
          // The live reply failed its grounding check server-side — clear
          // it; a corrected, safe reply follows via more onToken calls.
          accumulated = ''
          patch({ interpretation: '' })
        },
        onConfirm: () => {
          // No UI action needed — every token shown so far is now final.
        },
        onDone: (data) => {
          accumulated = data.text || accumulated
          patch({
            streaming: false, interpretation: data.text,
            response_source: data.response_source, notable_insight: data.notable_insight,
          })
        },
        onError: (message) => {
          patch({ streaming: false, interpretation: `Connection error: ${message}`, intent: 'Error' })
        },
      })
    } catch (err) {
      patch({
        streaming: false,
        interpretation: 'Connection error. Ensure the KAVACH backend is running on port 8000.',
        intent: 'Error',
      })
    } finally {
      setLoading(false)
    }
  }, [input, loading, sessionId, language, attachedDoc])

  // Voice input — errors used to fail completely silently (setRecording(false)
  // with no feedback at all), which is almost certainly what "the mic doesn't
  // work" actually meant in practice: it wasn't that recognition never ran,
  // it's that a permission-denied / no-speech / unsupported-language failure
  // gave no sign anything had gone wrong. Every failure path now surfaces a
  // clear, translated message.
  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { setMicNotice(t('chatMicError')); return }
    if (recording) {
      recognitionRef.current?.stop()
      setRecording(false)
      return
    }
    setMicNotice(null)
    const rec = new SR()
    rec.lang = language === 'kn' ? 'kn-IN' : 'en-IN'
    rec.interimResults = false
    rec.onresult = e => {
      const transcript = e.results[0][0].transcript
      setInput(transcript)
      setRecording(false)
      setTimeout(() => send(transcript), 100)
    }
    rec.onerror = (e) => {
      setRecording(false)
      if (e.error === 'not-allowed' || e.error === 'permission-denied') {
        setMicNotice(t('chatMicNotAllowed'))
      } else if (e.error === 'no-speech') {
        setMicNotice(t('chatMicNoSpeech'))
      } else if (e.error === 'language-not-supported' && language === 'kn') {
        setMicNotice(t('chatMicLangUnsupported'))
      } else {
        setMicNotice(t('chatMicError'))
      }
    }
    rec.onend = () => setRecording(false)
    recognitionRef.current = rec
    try {
      rec.start()
      setRecording(true)
    } catch {
      setMicNotice(t('chatMicError'))
    }
  }

  // Backend-generated PDF export (replaces the old client-side jsPDF
  // export, which had no way to embed a Kannada-capable font and would
  // have rendered Kannada chat turns as blank boxes — see
  // backend/services/pdf_export.py). Scoped to the current session; the
  // full "everything since this login" export happens automatically on
  // logout instead (see App.jsx).
  const exportPDF = async () => {
    if (!sessionId || exporting) return
    setExporting(true)
    try {
      const blob = await exportChatHistoryPdf('session', sessionId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `KAVACH-Session-${sessionId}-${Date.now()}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('Export failed', e)
    } finally {
      setExporting(false)
    }
  }

  const clearChat = () => startNewSession()

  return (
    <>
      <Header title={t('navChat')} subtitle="Natural Language Crime Query" user={user} />

      <div className="chat-wrap">
        {/* History sidebar */}
        {showHistory && (
          <div style={{
            width: 260, borderRight: '1px solid #E2E8F0', background: '#F8FAFC',
            display: 'flex', flexDirection: 'column', flexShrink: 0,
          }}>
            <div style={{ padding: '12px 14px', borderBottom: '1px solid #E2E8F0', background: '#fff' }}>
              <button onClick={startNewSession} style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '8px', background: '#0B1D3A', color: '#C5A028', border: 'none',
                borderRadius: 6, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
              }}>
                <Plus size={13} /> {t('chatNewChat')}
              </button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
              <div style={{ fontSize: '0.62rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.08em', padding: '6px 8px' }}>
                {t('chatHistory')}
              </div>
              {historyLoading ? (
                <div style={{ padding: '1.5rem 1rem', textAlign: 'center', fontSize: '0.7rem', color: '#94A3B8' }}>
                  Loading…
                </div>
              ) : historyError ? (
                <div style={{ padding: '1.25rem 1rem', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.7rem', color: '#C0392B', marginBottom: 8 }}>
                    Couldn't load your past conversations.
                  </div>
                  <button onClick={loadSessionsList} style={{
                    fontSize: '0.68rem', padding: '4px 10px', borderRadius: 5,
                    border: '1px solid #E2E8F0', background: '#fff', cursor: 'pointer', color: '#475569',
                  }}>
                    Retry
                  </button>
                </div>
              ) : pastSessions.length === 0 ? (
                <div style={{ padding: '1.5rem 1rem', textAlign: 'center', fontSize: '0.7rem', color: '#94A3B8' }}>
                  No past conversations yet
                </div>
              ) : pastSessions.map(s => (
                <button key={s.session_id} onClick={() => loadSession(s.session_id)} style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '9px 10px',
                  background: s.session_id === sessionId ? '#EFF6FF' : '#fff',
                  border: `1px solid ${s.session_id === sessionId ? '#BFDBFE' : '#E2E8F0'}`,
                  borderRadius: 6, marginBottom: 6, cursor: 'pointer',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 3 }}>
                    <MessageSquare size={10} color="#94A3B8" />
                    <span style={{ fontSize: '0.6rem', color: '#94A3B8' }}>
                      {new Date(s.last_active).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} · {s.turn_count} turns
                    </span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.first_message || '(empty)'}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Main chat */}
        <div className="chat-main">
          {/* Sub-header bar */}
          <div style={{
            background: '#fff', borderBottom: '1px solid #E2E8F0',
            padding: '6px 1rem', display: 'flex', alignItems: 'center',
            gap: 10, flexShrink: 0,
          }}>
            <button
              onClick={() => { const next = !showHistory; setShowHistory(next); if (next) loadSessionsList() }}
              title="Conversation history"
              style={{
                display: 'flex', alignItems: 'center', gap: 5, padding: '4px 8px',
                background: showHistory ? '#0B1D3A' : '#F8FAFC', border: '1px solid #E2E8F0',
                borderRadius: 5, cursor: 'pointer', fontSize: '0.7rem', fontWeight: 600,
                color: showHistory ? '#C5A028' : '#475569',
              }}
            >
              <History size={12} /> {t('chatHistory')}
            </button>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: '#0F7A5A',
              boxShadow: '0 0 0 2px rgba(15,122,90,0.25)',
            }}/>
            <span style={{ fontSize: '0.7rem', color: '#64748B' }}>
              {sessionId ? `Session: ${sessionId}` : 'Ready'} ●{' '}
              {language === 'en' ? 'English' : 'ಕನ್ನಡ'} mode
            </span>
            <div style={{ flex: 1 }} />
            <button onClick={exportPDF} disabled={!sessionId || exporting} title={!sessionId ? 'Send a message first' : undefined} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: '0.7rem', padding: '4px 10px',
              background: '#F8FAFC', border: '1px solid #E2E8F0',
              borderRadius: 5, cursor: (!sessionId || exporting) ? 'not-allowed' : 'pointer',
              color: '#475569', opacity: (!sessionId || exporting) ? 0.5 : 1,
            }}>
              <FileDown size={11} /> {exporting ? '…' : t('exportPdf')}
            </button>
            <button onClick={clearChat} style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: '0.7rem', padding: '4px 10px',
              background: '#FEF2F2', border: '1px solid #FECACA',
              borderRadius: 5, cursor: 'pointer', color: '#991B1B',
            }}>
              <Trash2 size={11} /> Clear
            </button>
          </div>

          {/* Messages */}
          <div className="chat-messages">
            {restoring && (
              <div style={{ textAlign: 'center', padding: '2rem', color: '#94A3B8', fontSize: '0.75rem' }}>
                Restoring your conversation…
              </div>
            )}
            {/* Starters (show when only welcome message) */}
            {!restoring && messages.length <= 1 && (
              <div style={{ padding: '8px 0' }}>
                <p style={{ fontSize: '0.7rem', color: '#94A3B8', marginBottom: 12, textAlign: 'center' }}>
                  — Try one of these queries to get started —
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
                  {STARTERS[language].map((s, i) => (
                    <button key={i} className="suggestion-chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              msg.type === 'user'
                ? <UserMessage key={i} text={msg.text} time={msg.time} />
                : <AIMessage
                    key={i} msg={msg} idx={i} t={t}
                    onViewNetwork={id => window.open(`/network?focus=${id}`, '_self')}
                    onViewProfile={id => window.open(`/profiles?id=${id}`, '_self')}
                    onSuggestionClick={send}
                    speakingId={speakingId}
                    onToggleSpeak={toggleSpeak}
                    sessionId={sessionId}
                  />
            ))}

            <div ref={messagesEndRef} />
          </div>

          {/* Mic notice — replaces the old silent failure on any voice-input error */}
          {micNotice && (
            <div style={{
              margin: '0 1rem', padding: '6px 10px', background: '#FFFBEB',
              border: '1px solid #FDE68A', borderRadius: 5, fontSize: '0.68rem',
              color: '#78350F', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <AlertCircle size={12} />
              {micNotice}
            </div>
          )}

          {/* Document-attach chip + notice — chat-with-a-PDF (see
              document_context.py). The document is scratch context for
              THIS chat session only, never the case database, until an
              officer explicitly extracts and confirms it. */}
          {attachedDoc && (
            <div className="doc-attach-chip">
              <FileText size={12} />
              <span>{attachedDoc.filename} attached · {attachedDoc.char_count.toLocaleString('en-IN')} chars</span>
              <button onClick={handleDetachDocument} title="Remove this document from the chat">
                <X size={12} />
              </button>
            </div>
          )}
          {docNotice && (
            <div style={{
              margin: '0 1rem 0.5rem', padding: '6px 10px',
              background: docNotice.type === 'error' ? '#FEF2F2' : '#F0FDF4',
              border: `1px solid ${docNotice.type === 'error' ? '#FECACA' : '#BBF7D0'}`,
              borderRadius: 5, fontSize: '0.68rem',
              color: docNotice.type === 'error' ? '#991B1B' : '#166534',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <AlertCircle size={12} />
              {docNotice.text}
            </div>
          )}

          {/* Input bar */}
          <div className="chat-input-bar">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg"
              style={{ display: 'none' }}
              onChange={e => handleAttachDocument(e.target.files?.[0])}
            />
            <button
              className="voice-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingDoc}
              title="Attach a PDF or photo to chat with (FIR, report, etc.)"
            >
              <Paperclip size={15} />
            </button>

            <button
              className={`voice-btn${recording ? ' recording' : ''}`}
              onClick={toggleVoice}
              title={recording ? 'Stop recording' : `Voice input (${language === 'kn' ? 'Kannada' : 'English'})`}
            >
              {recording ? <MicOff size={15} /> : <Mic size={15} />}
            </button>

            <textarea
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  send()
                }
              }}
              placeholder={uploadingDoc ? 'Extracting document text…' : t('chatPlaceholder')}
              rows={1}
            />

            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              style={{
                width: 38, height: 38, borderRadius: 6, border: 'none',
                background: input.trim() && !loading ? '#0B1D3A' : '#E2E8F0',
                color: input.trim() && !loading ? '#C5A028' : '#94A3B8',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'all 0.15s', flexShrink: 0,
              }}
            >
              <Send size={14} />
            </button>
          </div>
        </div>

        {/* Side panel */}
        <div className="chat-panel">
          <div style={{
            padding: '10px 14px', background: '#fff',
            borderBottom: '1px solid #E2E8F0', flexShrink: 0,
          }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1E293B' }}>
              {panelTitle}
            </div>
            <div style={{ fontSize: '0.62rem', color: '#94A3B8', marginTop: 2 }}>
              Click any card to explore
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
            {panelResults.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2rem 1rem' }}>
                <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>🔍</div>
                <div style={{ fontSize: '0.75rem', color: '#94A3B8', lineHeight: 1.6 }}>
                  Query results will appear here after you send a message
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {panelResults.map((r, i) => (
                  <ResultCard
                    key={i} row={r}
                    onViewNetwork={id => window.open(`/network?focus=${id}`, '_self')}
                    onViewProfile={id => window.open(`/profiles?id=${id}`, '_self')}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Disclaimer — honest about current data provenance (see
              backend/import_real_dataset.py): this stays up only while
              the system runs on placeholder data, not indefinitely. */}
          <div style={{
            padding: '8px 14px',
            borderTop: '1px solid #E2E8F0',
            fontSize: '0.6rem', color: '#94A3B8', lineHeight: 1.5,
            background: '#fff',
          }}>
            ⚠ {t('chatSynthDataNotice')}
          </div>
        </div>
      </div>
    </>
  )
}
