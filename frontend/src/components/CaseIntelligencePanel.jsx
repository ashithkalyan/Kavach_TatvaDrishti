import { useState, useEffect } from 'react'
import {
  getCaseRecommendations, submitLeadFeedback,
  getCaseBriefing, addCaseNote, resolveCaseNote,
} from '../services/api'
import { ThumbsUp, ThumbsDown, HelpCircle, Plus, CheckCircle, Users } from 'lucide-react'

const NOTE_KIND_LABELS = {
  important_person: 'Important Person',
  unresolved_thread: 'Unresolved Thread',
  failed_lead: 'Dead End',
  general: 'Note',
}
const NOTE_KIND_COLORS = {
  important_person: { bg: '#F5F3FF', border: '#DDD6FE', text: '#6B21A8' },
  unresolved_thread: { bg: '#FFFBEB', border: '#FDE68A', text: '#92400E' },
  failed_lead: { bg: '#F8FAFC', border: '#E2E8F0', text: '#64748B' },
  general: { bg: '#F0FDF4', border: '#BBF7D0', text: '#166534' },
}
const PRIORITY_COLORS = { urgent: '#C0392B', high: '#E67E22', standard: '#64748B' }

/*
  Case Outcome Feedback Loop (Feature 2): shows KAVACH's recommended
  investigative leads for this case, and lets an officer record what
  actually happened — see backend brain/feedback_engine.py. Leads that
  already have a track record show "X% of officers found this useful"
  evidence right alongside them.
*/
export function RecommendedLeads({ firNumber, crimeType }) {
  const [leads, setLeads] = useState(null)
  const [feedbackGiven, setFeedbackGiven] = useState({})

  useEffect(() => {
    setLeads(null)
    getCaseRecommendations(firNumber)
      .then(d => {
        setLeads(d.leads || [])
        const existing = {}
        Object.entries(d.existing_feedback || {}).forEach(([key, f]) => { existing[key] = f.outcome })
        setFeedbackGiven(existing)
      })
      .catch(() => setLeads([]))
  }, [firNumber])

  async function handleFeedback(lead, outcome) {
    setFeedbackGiven(prev => ({ ...prev, [lead.key]: outcome }))
    try {
      await submitLeadFeedback(firNumber, { lead_key: lead.key, lead_text: lead.lead, crime_type: crimeType, outcome })
    } catch {
      // best-effort — the optimistic UI state stays either way, a retry
      // on next view will re-sync from the server
    }
  }

  if (leads === null) return <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Loading recommended leads…</div>
  if (leads.length === 0) return null

  return (
    <div style={{ marginBottom: 14 }}>
      <div className="section-title">Recommended Leads ({leads.length})</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {leads.map(lead => {
          const given = feedbackGiven[lead.key]
          const stats = lead.feedback
          return (
            <div key={lead.key} style={{ padding: '9px 12px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6 }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <span style={{
                  fontSize: '0.58rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
                  color: PRIORITY_COLORS[lead.priority] || '#64748B', flexShrink: 0, marginTop: 2, width: 50,
                }}>{lead.priority}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.78rem', color: '#1E293B' }}>{lead.lead}</div>
                  {stats && stats.total_feedback > 0 && (
                    <div style={{ fontSize: '0.62rem', color: '#94A3B8', marginTop: 3 }}>
                      {stats.useful_rate_pct !== null
                        ? `${stats.useful_rate_pct}% of officers found this useful across ${stats.total_feedback} case${stats.total_feedback === 1 ? '' : 's'}`
                        : `${stats.total_feedback} case(s) marked inconclusive so far`}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
                  <button title="Useful" onClick={() => handleFeedback(lead, 'useful')} style={{
                    background: given === 'useful' ? '#D1FAE5' : 'none', border: '1px solid #E2E8F0', borderRadius: 4,
                    cursor: 'pointer', padding: 4, display: 'flex', color: given === 'useful' ? '#065F46' : '#94A3B8',
                  }}><ThumbsUp size={12} /></button>
                  <button title="Not useful" onClick={() => handleFeedback(lead, 'not_useful')} style={{
                    background: given === 'not_useful' ? '#FEE2E2' : 'none', border: '1px solid #E2E8F0', borderRadius: 4,
                    cursor: 'pointer', padding: 4, display: 'flex', color: given === 'not_useful' ? '#991B1B' : '#94A3B8',
                  }}><ThumbsDown size={12} /></button>
                  <button title="Inconclusive" onClick={() => handleFeedback(lead, 'inconclusive')} style={{
                    background: given === 'inconclusive' ? '#FEF3C7' : 'none', border: '1px solid #E2E8F0', borderRadius: 4,
                    cursor: 'pointer', padding: 4, display: 'flex', color: given === 'inconclusive' ? '#92400E' : '#94A3B8',
                  }}><HelpCircle size={12} /></button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/*
  Investigation Knowledge Surviving Officer Transfer (Feature 4): case
  notes tagged by kind, an unresolved-thread resolve action, and who's
  worked the case — see backend brain/case_memory.py. Deliberately
  case-scoped, not officer-scoped, so it's exactly as visible to
  whichever officer opens this FIR next.
*/
export function CaseNotesSection({ firNumber }) {
  const [notes, setNotes] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [newKind, setNewKind] = useState('general')
  const [newText, setNewText] = useState('')
  const [saving, setSaving] = useState(false)

  function refresh() {
    getCaseBriefing(firNumber)
      .then(b => setNotes({
        important_people: b.important_people, unresolved_threads: b.unresolved_threads,
        resolved_threads: b.resolved_threads, failed_leads: b.failed_leads,
        general_notes: b.general_notes, officers_involved: b.officers_involved,
      }))
      .catch(() => setNotes(null))
  }

  useEffect(() => { refresh() }, [firNumber])

  async function handleAdd() {
    if (!newText.trim()) return
    setSaving(true)
    try {
      await addCaseNote(firNumber, { kind: newKind, note_text: newText.trim() })
      setNewText('')
      setShowAdd(false)
      refresh()
    } finally {
      setSaving(false)
    }
  }

  async function handleResolve(noteId) {
    await resolveCaseNote(firNumber, noteId, true)
    refresh()
  }

  if (!notes) return null
  const activeNotes = [...notes.important_people, ...notes.unresolved_threads, ...notes.failed_leads, ...notes.general_notes]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div className="section-title" style={{ marginBottom: 0 }}>
          Case Notes {activeNotes.length > 0 && `(${activeNotes.length})`}
          <span style={{ fontWeight: 400, color: '#94A3B8', fontSize: '0.62rem', marginLeft: 6 }}>— survives officer transfer</span>
        </div>
        <button onClick={() => setShowAdd(s => !s)} style={{
          display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.65rem', padding: '3px 8px',
          border: '1px solid #E2E8F0', borderRadius: 4, background: '#F8FAFC', cursor: 'pointer', color: '#475569',
        }}>
          <Plus size={10} /> Add note
        </button>
      </div>

      {notes.officers_involved?.length > 1 && (
        <div style={{ fontSize: '0.68rem', color: '#64748B', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
          <Users size={11} /> Worked by: {notes.officers_involved.join(', ')}
        </div>
      )}

      {showAdd && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 10, padding: 8, background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6 }}>
          <select value={newKind} onChange={e => setNewKind(e.target.value)}
            style={{ fontSize: '0.7rem', padding: '5px 6px', border: '1px solid #E2E8F0', borderRadius: 4 }}>
            {Object.entries(NOTE_KIND_LABELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
          <input value={newText} onChange={e => setNewText(e.target.value)} placeholder="Note text…"
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
            style={{ flex: 1, fontSize: '0.72rem', padding: '5px 8px', border: '1px solid #E2E8F0', borderRadius: 4 }} />
          <button onClick={handleAdd} disabled={saving || !newText.trim()} style={{
            fontSize: '0.7rem', padding: '5px 10px', border: 'none', borderRadius: 4,
            background: '#0B1D3A', color: '#C5A028', cursor: saving || !newText.trim() ? 'not-allowed' : 'pointer',
          }}>{saving ? '…' : 'Save'}</button>
        </div>
      )}

      {activeNotes.length === 0 ? (
        <p style={{ color: '#94A3B8', fontSize: '0.75rem' }}>No notes yet — the first officer to leave one helps whoever picks this case up next.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {activeNotes.map(n => {
            const colors = NOTE_KIND_COLORS[n.kind]
            return (
              <div key={n.note_id} style={{ padding: '8px 10px', background: colors.bg, border: `1px solid ${colors.border}`, borderRadius: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                  <div>
                    <span style={{ fontSize: '0.6rem', fontWeight: 700, color: colors.text, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {NOTE_KIND_LABELS[n.kind]}
                    </span>
                    <div style={{ fontSize: '0.75rem', color: '#1E293B', marginTop: 2 }}>{n.note_text}</div>
                    <div style={{ fontSize: '0.6rem', color: '#94A3B8', marginTop: 3 }}>
                      {n.officer_name || 'Unknown officer'} · {n.created_at?.slice(0, 16)}
                    </div>
                  </div>
                  {n.kind === 'unresolved_thread' && (
                    <button onClick={() => handleResolve(n.note_id)} title="Mark resolved" style={{
                      background: 'none', border: '1px solid #E2E8F0', borderRadius: 4, cursor: 'pointer',
                      padding: '3px 6px', fontSize: '0.6rem', color: '#065F46', flexShrink: 0,
                      display: 'flex', alignItems: 'center', gap: 3, whiteSpace: 'nowrap',
                    }}><CheckCircle size={10} /> Resolve</button>
                  )}
                </div>
              </div>
            )
          })}
          {notes.resolved_threads?.length > 0 && (
            <details style={{ fontSize: '0.68rem', color: '#94A3B8' }}>
              <summary style={{ cursor: 'pointer' }}>{notes.resolved_threads.length} resolved thread(s)</summary>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                {notes.resolved_threads.map(n => (
                  <div key={n.note_id} style={{ padding: '6px 8px', background: '#F8FAFC', borderRadius: 4, textDecoration: 'line-through' }}>
                    {n.note_text}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
