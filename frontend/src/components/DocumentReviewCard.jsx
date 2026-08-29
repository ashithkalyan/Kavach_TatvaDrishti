import { useState, useEffect } from 'react'
import { LabeledInput, LabeledSelect, LabeledTextarea, PersonListEditor } from './FormFields'
import { confirmIngest, getDistricts, getPoliceStations, getCrimeSubheads, saveChatDocumentResult } from '../services/api'
import { CheckCircle, AlertCircle, FileText, ShieldQuestion } from 'lucide-react'

function normaliseDateGuess(raw) {
  if (!raw) return ''
  const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (iso) return raw
  const dmy = raw.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/)
  if (dmy) return `${dmy[3]}-${dmy[2].padStart(2, '0')}-${dmy[1].padStart(2, '0')}`
  return ''
}

function draftToForm(d) {
  return {
    crime_no: d.crime_no_guess || '',
    case_no: (d.crime_no_guess || '').slice(-9) || '',
    registration_date: normaliseDateGuess(d.date_guess),
    district: d.districts_detected?.[0] || '',
    police_station_id: '',
    crime_minor_head_id: '',
    brief_facts: d.raw_text_preview?.slice(0, 300) || '',
    accused: (d.person_name_candidates?.length ? d.person_name_candidates.slice(0, 1) : ['']).map(n => ({ name: n, age: d.age_guess || '', gender: '' })),
    victims: [],
  }
}

/*
  Same review-before-save contract as Cases.jsx's UploadModal — every
  field is editable, and NOTHING reaches the database until "Confirm &
  Save" is clicked (which calls the exact same confirmIngest() ->
  POST /api/ingest/confirm the Cases page uses). Rendered inline in the
  chat thread (see pages/CrimeChat.jsx) instead of as a modal, since the
  document was already extracted by the time this renders — there's no
  upload step here, just review.

  `sessionId` + `initialSaveResult`: after a successful save, the
  outcome is persisted server-side (see saveChatDocumentResult()) so
  that switching chat sessions and back — or reloading the page —
  restores the "Saved" confirmation below instead of reverting to the
  blank edit form (a reported bug). `initialSaveResult`, when passed by
  CrimeChat.jsx's loadSession(), skips straight to that confirmed state
  on mount.
*/
export default function DocumentReviewCard({ draft, filename, sessionId, initialSaveResult = null }) {
  const [form, setForm] = useState(() => draftToForm(draft))
  const [districts, setDistricts] = useState([])
  const [stations, setStations] = useState([])
  const [crimeSubheads, setCrimeSubheads] = useState([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saveResult, setSaveResult] = useState(initialSaveResult)

  useEffect(() => {
    getDistricts().then(d => setDistricts(d.districts || [])).catch(() => {})
    getCrimeSubheads().then(d => setCrimeSubheads(d.crime_subheads || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!form.district) { setStations([]); return }
    getPoliceStations(form.district).then(d => setStations(d.police_stations || [])).catch(() => {})
  }, [form.district])

  function updatePerson(listKey, idx, field, value) {
    setForm(f => {
      const list = [...f[listKey]]
      list[idx] = { ...list[idx], [field]: value }
      return { ...f, [listKey]: list }
    })
  }
  function addPerson(listKey) {
    setForm(f => ({ ...f, [listKey]: [...f[listKey], { name: '', age: '', gender: '' }] }))
  }
  function removePerson(listKey, idx) {
    setForm(f => ({ ...f, [listKey]: f[listKey].filter((_, i) => i !== idx) }))
  }

  async function handleConfirm() {
    setSaving(true); setSaveError('')
    try {
      const payload = {
        crime_no: form.crime_no.trim(),
        case_no: form.case_no.trim(),
        registration_date: form.registration_date,
        police_station_id: Number(form.police_station_id),
        crime_minor_head_id: form.crime_minor_head_id ? Number(form.crime_minor_head_id) : null,
        brief_facts: form.brief_facts,
        accused: form.accused.filter(a => a.name.trim()).map(a => ({ ...a, age: a.age ? Number(a.age) : null })),
        victims: form.victims.filter(v => v.name.trim()).map(v => ({ ...v, age: v.age ? Number(v.age) : null })),
      }
      const res = await confirmIngest(payload)
      setSaveResult(res)
      if (sessionId) {
        // Best-effort — the case is already saved regardless of whether
        // this persistence call succeeds; it only affects whether the
        // "Saved" box survives a reload.
        saveChatDocumentResult(sessionId, res).catch(() => {})
      }
    } catch (err) {
      setSaveError(err?.response?.data?.detail || 'Could not save this record — check the fields above and try again.')
    } finally {
      setSaving(false)
    }
  }

  const formValid = form.crime_no.trim() && form.case_no.trim() && form.registration_date && form.police_station_id
  const matchedHints = (draft.identity_hints || []).filter(h => h.possible_existing_match)

  if (saveResult) {
    return (
      <div style={cardStyle}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '12px 14px', background: '#D1FAE5', borderRadius: 8 }}>
          <CheckCircle size={18} color="#065F46" style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#065F46' }}>Saved — FIR {saveResult.fir_number} is now live</div>
            <div style={{ fontSize: '0.68rem', color: '#065F46', marginTop: 3 }}>{saveResult.note}</div>
          </div>
        </div>
        {saveResult.accused?.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
            {saveResult.accused.map((a, i) => (
              <div key={i} style={{ padding: '7px 9px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.7rem' }}>
                <strong>{a.name}</strong> — {a.linked_to_existing_identity
                  ? <span>linked to an existing identity (matched "{a.matched_against}", {Math.round(a.match_confidence * 100)}% confidence)</span>
                  : <span>new identity created</span>}
                {' '}· risk score <strong>{a.risk_score}</strong> ({a.risk_category})
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <FileText size={14} color="#C5A028" />
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#0B1D3A' }}>{filename}</span>
        <span style={{ fontSize: '0.65rem', color: '#94A3B8' }}>— review draft, nothing saved yet</span>
      </div>

      <div style={{ padding: '7px 10px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 5, fontSize: '0.68rem', color: '#1D4ED8', marginBottom: 10 }}>
        Every field below is editable — review and correct anything the extraction got wrong before saving. Nothing reaches the database until you click "Confirm & Save".
      </div>

      {draft.extraction_notes?.length > 0 && (
        <div style={{ padding: '7px 10px', background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 5, fontSize: '0.68rem', color: '#78350F', marginBottom: 10 }}>
          <strong>⚠ Review needed:</strong>
          <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>
            {draft.extraction_notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      {matchedHints.length > 0 && (
        <div style={{ display: 'flex', gap: 8, padding: '7px 10px', background: '#F3E8FF', border: '1px solid #D8B4FE', borderRadius: 5, fontSize: '0.68rem', color: '#6B21A8', marginBottom: 10 }}>
          <ShieldQuestion size={13} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <strong>Possible existing record(s):</strong>{' '}
            {matchedHints.map((h, i) => (
              <span key={i}>{h.name} (matched "{h.matched_against}", {Math.round((h.match_confidence || 0) * 100)}% confidence){i < matchedHints.length - 1 ? '; ' : ''}</span>
            ))}
            {' '}— resolved for real when you confirm.
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <LabeledInput label="Crime Number (18-digit)" value={form.crime_no}
            onChange={v => setForm(f => ({ ...f, crime_no: v }))} mono />
          <LabeledInput label="Case Number" value={form.case_no}
            onChange={v => setForm(f => ({ ...f, case_no: v }))} mono />
          <LabeledInput label="Registration Date" type="date" value={form.registration_date}
            onChange={v => setForm(f => ({ ...f, registration_date: v }))} />
          <LabeledSelect label="District" value={form.district}
            onChange={v => setForm(f => ({ ...f, district: v, police_station_id: '' }))}
            options={districts.map(d => ({ value: d, label: d }))} placeholder="Select district" />
          <LabeledSelect label="Police Station" value={form.police_station_id}
            onChange={v => setForm(f => ({ ...f, police_station_id: v }))}
            options={stations.map(s => ({ value: s.id, label: s.name }))}
            placeholder={form.district ? 'Select station' : 'Select a district first'}
            disabled={!form.district} />
          <LabeledSelect label="Crime Type" value={form.crime_minor_head_id}
            onChange={v => setForm(f => ({ ...f, crime_minor_head_id: v }))}
            options={crimeSubheads.map(c => ({ value: c.id, label: c.name }))} placeholder="Select crime type" />
        </div>

        <LabeledTextarea label="Brief Facts" value={form.brief_facts}
          onChange={v => setForm(f => ({ ...f, brief_facts: v }))} />

        <PersonListEditor title="Accused" list={form.accused}
          onAdd={() => addPerson('accused')} onRemove={i => removePerson('accused', i)}
          onChange={(i, field, v) => updatePerson('accused', i, field, v)} />
        <PersonListEditor title="Victims" list={form.victims}
          onAdd={() => addPerson('victims')} onRemove={i => removePerson('victims', i)}
          onChange={(i, field, v) => updatePerson('victims', i, field, v)} />

        {saveError && (
          <div style={{ display: 'flex', gap: 8, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, padding: '8px 10px', fontSize: '0.7rem', color: '#991B1B' }}>
            <AlertCircle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
            {saveError}
          </div>
        )}

        <button onClick={handleConfirm} disabled={!formValid || saving} style={{
          padding: '9px', background: formValid && !saving ? '#0B1D3A' : '#CBD5E1',
          border: 'none', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700,
          color: formValid && !saving ? '#C5A028' : '#F1F5F9',
          cursor: formValid && !saving ? 'pointer' : 'not-allowed',
        }}>
          {saving ? 'Saving…' : 'Confirm & Save'}
        </button>
      </div>
    </div>
  )
}

const cardStyle = {
  border: '1px solid #E2E8F0', borderRadius: 10, padding: '12px 14px',
  background: '#fff', marginTop: 8, maxWidth: 520,
}
