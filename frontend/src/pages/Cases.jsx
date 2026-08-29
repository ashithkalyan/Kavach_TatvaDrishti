import { useState, useEffect } from 'react'
import {
  searchFIRs, getFIRDetail, getDistricts, getCrimeTypes, ingestDocument, getCaseSummary,
  confirmIngest, getPoliceStations, getCrimeSubheads,
} from '../services/api'
import Header from '../components/Header'
import { LabeledInput, LabeledSelect, LabeledTextarea, PersonListEditor } from '../components/FormFields'
import { RecommendedLeads, CaseNotesSection } from '../components/CaseIntelligencePanel'
import {
  Search, Filter, ChevronDown, X, Eye, AlertCircle, MapPin, Calendar, User, Clock,
  Upload, FileText, CheckCircle, Sparkles, Loader2,
} from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

function statusClass(s) {
  if (s === 'Under Investigation') return 'status-pill status-open'
  if (s === 'Charge-Sheeted') return 'status-pill status-sheeted'
  if (s === 'Closed') return 'status-pill status-closed'
  return 'status-pill status-filed'
}

function UploadModal({ onClose }) {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  // Confirm-form state — populated from the extracted draft, but every
  // field is editable, and NOTHING here is written to the database
  // until the officer explicitly clicks "Confirm & Save".
  const [form, setForm] = useState(null)
  const [districts, setDistricts] = useState([])
  const [stations, setStations] = useState([])
  const [crimeSubheads, setCrimeSubheads] = useState([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [saveResult, setSaveResult] = useState(null)

  useEffect(() => {
    getDistricts().then(d => setDistricts(d.districts || [])).catch(() => {})
    getCrimeSubheads().then(d => setCrimeSubheads(d.crime_subheads || [])).catch(() => {})
  }, [])

  useEffect(() => {
    if (!form?.district) { setStations([]); return }
    getPoliceStations(form.district).then(d => setStations(d.police_stations || [])).catch(() => {})
  }, [form?.district])

  async function handleUpload(f) {
    if (!f) return
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg']
    if (!validTypes.includes(f.type)) {
      setError('Only PDF, PNG, or JPG files are supported.')
      return
    }
    setFile(f); setUploading(true); setError(''); setResult(null); setSaveResult(null); setSaveError('')
    try {
      const data = await ingestDocument(f)
      setResult(data)
      if (data.draft) {
        const d = data.draft
        setForm({
          crime_no: d.crime_no_guess || '',
          case_no: (d.crime_no_guess || '').slice(-9) || '',
          registration_date: normaliseDateGuess(d.date_guess),
          district: d.districts_detected?.[0] || '',
          police_station_id: '',
          crime_minor_head_id: '',
          brief_facts: d.raw_text_preview?.slice(0, 300) || '',
          accused: (d.person_name_candidates?.length ? d.person_name_candidates.slice(0, 1) : ['']).map(n => ({ name: n, age: d.age_guess || '', gender: '' })),
          victims: [],
        })
      }
    } catch (err) {
      setError(err?.response?.data?.detail || 'Extraction failed. The file may be corrupted or unreadable.')
    } finally {
      setUploading(false)
    }
  }

  function normaliseDateGuess(raw) {
    if (!raw) return ''
    // Handles DD/MM/YYYY, DD-MM-YYYY, and already-ISO YYYY-MM-DD guesses
    const iso = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/)
    if (iso) return raw
    const dmy = raw.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/)
    if (dmy) return `${dmy[3]}-${dmy[2].padStart(2, '0')}-${dmy[1].padStart(2, '0')}`
    return ''
  }

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
    } catch (err) {
      setSaveError(err?.response?.data?.detail || 'Could not save this record — check the fields above and try again.')
    } finally {
      setSaving(false)
    }
  }

  const formValid = form && form.crime_no.trim() && form.case_no.trim() && form.registration_date && form.police_station_id

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: '1rem', backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, width: '100%', maxWidth: 620,
        maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 24px 64px rgba(0,0,0,0.25)', overflow: 'hidden',
      }}>
        <div style={{ background: '#0B1D3A', padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <Upload size={16} color="#C5A028" />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#fff' }}>Ingest New FIR Document</div>
            <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.5)' }}>PDF or scanned photo — extracted fields require your confirmation before they enter the database</div>
          </div>
          <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', width: 26, height: 26, cursor: 'pointer', color: '#fff' }}>
            <X size={13} />
          </button>
        </div>

        <div style={{ padding: '1.25rem', overflowY: 'auto' }}>
          {!file && (
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); handleUpload(e.dataTransfer.files[0]) }}
              style={{
                border: `2px dashed ${dragging ? '#C5A028' : '#E2E8F0'}`, borderRadius: 10,
                padding: '2.5rem 1.5rem', textAlign: 'center',
                background: dragging ? '#FFFBEB' : '#F8FAFC', transition: 'all 0.15s',
              }}
            >
              <Upload size={28} color="#94A3B8" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: '0.82rem', color: '#475569', marginBottom: 6 }}>Drag and drop a file here, or</p>
              <label style={{
                display: 'inline-block', padding: '7px 16px', background: '#0B1D3A', color: '#C5A028',
                borderRadius: 6, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
              }}>
                Browse Files
                <input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e => handleUpload(e.target.files[0])} style={{ display: 'none' }} />
              </label>
              <p style={{ fontSize: '0.65rem', color: '#94A3B8', marginTop: 10 }}>PDF, PNG, or JPG · Text extraction via pdfplumber/Tesseract OCR, fully local</p>
            </div>
          )}

          {uploading && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#64748B' }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', border: '3px solid #E2E8F0', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
              Extracting text from {file?.name}…
            </div>
          )}

          {error && (
            <div style={{ display: 'flex', gap: 8, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, padding: '10px 12px', fontSize: '0.78rem', color: '#991B1B', marginTop: 12 }}>
              <AlertCircle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              {error}
            </div>
          )}

          {/* Success state — the record is genuinely live now */}
          {saveResult && (
            <div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '14px', background: '#D1FAE5', borderRadius: 8, marginBottom: 14 }}>
                <CheckCircle size={20} color="#065F46" style={{ flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#065F46' }}>Saved — FIR {saveResult.fir_number} is now live</div>
                  <div style={{ fontSize: '0.72rem', color: '#065F46', marginTop: 3 }}>{saveResult.note}</div>
                </div>
              </div>
              {saveResult.accused?.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  {saveResult.accused.map((a, i) => (
                    <div key={i} style={{ padding: '8px 10px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.75rem' }}>
                      <strong>{a.name}</strong> — {a.linked_to_existing_identity
                        ? <span>linked to an existing identity (matched "{a.matched_against}", {Math.round(a.match_confidence * 100)}% confidence)</span>
                        : <span>new identity created</span>}
                      {' '}· risk score <strong>{a.risk_score}</strong> ({a.risk_category})
                    </div>
                  ))}
                </div>
              )}
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => { setFile(null); setResult(null); setForm(null); setSaveResult(null) }} style={{
                  flex: 1, padding: '8px', background: '#F8FAFC', border: '1px solid #E2E8F0',
                  borderRadius: 6, fontSize: '0.75rem', fontWeight: 600, color: '#475569', cursor: 'pointer',
                }}>
                  Ingest Another Document
                </button>
                <button onClick={onClose} style={{
                  flex: 1, padding: '8px', background: '#0B1D3A', border: 'none',
                  borderRadius: 6, fontSize: '0.75rem', fontWeight: 600, color: '#C5A028', cursor: 'pointer',
                }}>
                  Done
                </button>
              </div>
            </div>
          )}

          {/* Review + confirm form */}
          {result && !uploading && !saveResult && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '10px 12px', background: result.success ? '#D1FAE5' : '#FEF3C7', borderRadius: 6 }}>
                {result.success ? <CheckCircle size={16} color="#065F46" /> : <AlertCircle size={16} color="#92400E" />}
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: result.success ? '#065F46' : '#92400E' }}>
                  {result.success ? `Extracted via ${result.extraction.engine}` : 'Extraction returned no usable text'}
                </span>
              </div>

              {result.draft && form && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ padding: '8px 10px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 5, fontSize: '0.7rem', color: '#1D4ED8' }}>
                    Every field below is editable — review and correct anything the extraction got wrong before saving. Nothing reaches the database until you click "Confirm & Save".
                  </div>

                  {result.draft.extraction_notes?.length > 0 && (
                    <div style={{ padding: '8px 10px', background: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: 5, fontSize: '0.7rem', color: '#78350F' }}>
                      <strong>⚠ Review needed:</strong>
                      <ul style={{ margin: '4px 0 0', paddingLeft: 16 }}>
                        {result.draft.extraction_notes.map((n, i) => <li key={i}>{n}</li>)}
                      </ul>
                    </div>
                  )}

                  {/* Core case fields */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <LabeledInput label="Crime Number (18-digit)" value={form.crime_no}
                      onChange={v => setForm(f => ({ ...f, crime_no: v }))} mono />
                    <LabeledInput label="Case Number" value={form.case_no}
                      onChange={v => setForm(f => ({ ...f, case_no: v }))} mono />
                    <LabeledInput label="Registration Date" type="date" value={form.registration_date}
                      onChange={v => setForm(f => ({ ...f, registration_date: v }))} />
                    <LabeledSelect label="District" value={form.district}
                      onChange={v => setForm(f => ({ ...f, district: v, police_station_id: '' }))}
                      options={districts.map(d => ({ value: d, label: d }))} placeholder="Select a district" />
                    <LabeledSelect label="Police Station" value={form.police_station_id}
                      onChange={v => setForm(f => ({ ...f, police_station_id: v }))}
                      options={stations.map(s => ({ value: String(s.id), label: s.name }))}
                      placeholder={form.district ? 'Select a police station' : 'Select a district first'}
                      disabled={!form.district} />
                    <LabeledSelect label="Crime Type" value={form.crime_minor_head_id}
                      onChange={v => setForm(f => ({ ...f, crime_minor_head_id: v }))}
                      options={crimeSubheads.map(c => ({ value: String(c.id), label: c.name }))}
                      placeholder="Select a crime type" />
                  </div>

                  <LabeledTextarea label="Brief Facts" value={form.brief_facts}
                    onChange={v => setForm(f => ({ ...f, brief_facts: v }))} />

                  {/* Accused */}
                  <PersonListEditor
                    title="Accused Persons" listKey="accused" list={form.accused}
                    onAdd={() => addPerson('accused')}
                    onRemove={i => removePerson('accused', i)}
                    onChange={(i, field, v) => updatePerson('accused', i, field, v)}
                  />
                  <PersonListEditor
                    title="Victims" listKey="victims" list={form.victims}
                    onAdd={() => addPerson('victims')}
                    onRemove={i => removePerson('victims', i)}
                    onChange={(i, field, v) => updatePerson('victims', i, field, v)}
                  />

                  {saveError && (
                    <div style={{ display: 'flex', gap: 8, background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, padding: '10px 12px', fontSize: '0.76rem', color: '#991B1B' }}>
                      <AlertCircle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
                      {saveError}
                    </div>
                  )}

                  <button onClick={handleConfirm} disabled={!formValid || saving} style={{
                    marginTop: 4, width: '100%', padding: '10px', border: 'none', borderRadius: 6,
                    fontSize: '0.8rem', fontWeight: 700, cursor: (!formValid || saving) ? 'not-allowed' : 'pointer',
                    background: (!formValid || saving) ? '#E2E8F0' : '#0B1D3A',
                    color: (!formValid || saving) ? '#94A3B8' : '#C5A028',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  }}>
                    {saving ? <Loader2 size={14} className="spin" /> : <CheckCircle size={14} />}
                    {saving ? 'Saving…' : 'Confirm & Save to Database'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function FIRModal({ fir, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFIRDetail(fir.fir_number)
      .then(setDetail)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [fir.fir_number])

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: '1rem', backdropFilter: 'blur(3px)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 10,
        width: '100%', maxWidth: 680, maxHeight: '85vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        animation: 'slideUp 0.25s ease-out',
      }}>
        {/* Header */}
        <div style={{ background: '#0B1D3A', padding: '14px 18px', borderRadius: '10px 10px 0 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: '#C5A028', fontWeight: 700 }}>{fir.fir_number}</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff', marginTop: 2 }}>{fir.crime_type}</div>
          </div>
          <span className={statusClass(fir.status)} style={{ fontSize: '0.65rem' }}>{fir.status}</span>
          <button onClick={onClose} style={{ background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%', width: 26, height: 26, cursor: 'pointer', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <X size={13} />
          </button>
        </div>

        <div style={{ overflowY: 'auto', flex: 1 }}>
          {loading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#94A3B8' }}>Loading FIR details…</div>
          ) : detail ? (
            <div style={{ padding: '1.25rem 1.5rem' }}>
              {/* Meta */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                {[
                  { icon: Calendar, label: 'Registration Date', value: detail.registration_date },
                  { icon: Clock, label: 'Occurrence Date / Time', value: `${detail.occurrence_date} at ${detail.occurrence_time}` },
                  { icon: MapPin, label: 'Police Station', value: `${detail.police_station}, ${detail.district}` },
                  { icon: User, label: 'Investigating Officer', value: detail.investigating_officer },
                ].map(item => (
                  <div key={item.label} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <item.icon size={14} color="#94A3B8" style={{ marginTop: 2, flexShrink: 0 }} />
                    <div>
                      <div style={{ fontSize: '0.62rem', color: '#94A3B8', marginBottom: 1, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{item.label}</div>
                      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1E293B' }}>{item.value}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* IPC + description */}
              <div style={{ marginBottom: 14, padding: '10px 12px', background: '#F8FAFC', borderRadius: 6, border: '1px solid #E2E8F0' }}>
                <span style={{ fontFamily: 'monospace', fontSize: '0.72rem', fontWeight: 700, color: '#C5A028', background: '#0B1D3A', padding: '2px 8px', borderRadius: 3, marginRight: 8 }}>{detail.ipc_section}</span>
                <span style={{ fontSize: '0.78rem', color: '#334155' }}>{detail.crime_description}</span>
              </div>

              {detail.property_value > 0 && (
                <div style={{ marginBottom: 14, fontSize: '0.75rem', color: '#C0392B', fontWeight: 600 }}>
                  Property/Loss Value: ₹{detail.property_value?.toLocaleString('en-IN')}
                </div>
              )}

              {/* Accused */}
              {detail.accused?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div className="section-title">Accused ({detail.accused.length})</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {detail.accused.map(acc => (
                      <div key={acc.accused_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', background: '#F8FAFC', borderRadius: 6, border: '1px solid #E2E8F0' }}>
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#0B1D3A', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 700, color: '#C5A028', flexShrink: 0 }}>
                          {acc.name?.[0]}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E293B' }}>{acc.name}</div>
                          <div style={{ fontSize: '0.65rem', color: '#64748B' }}>{acc.role} • {acc.age} yrs • {acc.district}</div>
                        </div>
                        <span className={`risk-badge risk-${acc.risk_category}`}>{acc.risk_category}</span>
                        <span className={`status-pill ${acc.fa_arrested ? 'status-sheeted' : 'status-open'}`} style={{ fontSize: '0.6rem' }}>
                          {acc.fa_arrested ? 'Arrested' : 'At Large'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Victims */}
              {detail.victims?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div className="section-title">Victims ({detail.victims.length})</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {detail.victims.map(v => (
                      <div key={v.victim_id} style={{ padding: '7px 12px', background: '#FFF9F9', border: '1px solid #FEE2E2', borderRadius: 5, fontSize: '0.75rem' }}>
                        <span style={{ fontWeight: 600, color: '#1E293B' }}>{v.name}</span>
                        <span style={{ color: '#64748B' }}> — {v.age} yrs, {v.gender === 'M' ? 'Male' : 'Female'}</span>
                        {v.injury_description !== 'None' && <div style={{ fontSize: '0.68rem', color: '#C0392B', marginTop: 2 }}>{v.injury_description}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Investigation updates */}
              {detail.investigation_updates?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div className="section-title">Investigation Timeline</div>
                  <div style={{ borderLeft: '2px solid #E2E8F0', paddingLeft: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {detail.investigation_updates.map((u, i) => (
                      <div key={u.id} style={{ position: 'relative' }}>
                        <div style={{ position: 'absolute', left: -19, top: 4, width: 8, height: 8, borderRadius: '50%', background: i === 0 ? '#C5A028' : '#CBD5E1', border: '2px solid #fff' }} />
                        <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginBottom: 2 }}>{u.update_date} — {u.officer_name}</div>
                        <div style={{ fontSize: '0.75rem', color: '#334155' }}>{u.update_text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommended leads (Feature 2 — case outcome feedback loop) */}
              <RecommendedLeads firNumber={fir.fir_number} crimeType={detail.crime_type} />

              {/* Case notes (Feature 4 — institutional memory that survives officer transfer) */}
              <CaseNotesSection firNumber={fir.fir_number} />

              {/* Similar cases */}
              {detail.similar_cases?.length > 0 && (
                <div>
                  <div className="section-title">Similar Cases ({detail.similar_cases.length})</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {detail.similar_cases.map(c => (
                      <div key={c.fir_number} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#F8FAFC', borderRadius: 5, fontSize: '0.72rem' }}>
                        <span className="mono" style={{ color: '#1D4ED8', fontWeight: 600 }}>{c.fir_number}</span>
                        <span>{c.registration_date}</span>
                        <span className={statusClass(c.status)}>{c.status?.replace('Under Investigation','Investigating')}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: '#C0392B' }}>Failed to load FIR details.</div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Cases({ user }) {
  const { t } = useLanguage()
  const [firs, setFirs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [district, setDistrict] = useState('')
  const [crimeType, setCrimeType] = useState('')
  const [status, setStatus] = useState('')
  const [year, setYear] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedFIR, setSelectedFIR] = useState(null)
  const [showUpload, setShowUpload] = useState(false)
  const [districts, setDistricts] = useState([])
  const [crimeTypes, setCrimeTypes] = useState([])
  const LIMIT = 20

  useEffect(() => {
    Promise.all([getDistricts(), getCrimeTypes()])
      .then(([d, c]) => { setDistricts(d.districts); setCrimeTypes(c.crime_types) })
      .catch(console.error)
  }, [])

  useEffect(() => {
    setLoading(true)
    searchFIRs({ q: q || undefined, district: district || undefined, crime_type: crimeType || undefined, status: status || undefined, year: year || undefined, limit: LIMIT, offset })
      .then(d => { setFirs(d.results); setTotal(d.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [q, district, crimeType, status, year, offset])

  const pages = Math.ceil(total / LIMIT)
  const currentPage = Math.floor(offset / LIMIT) + 1

  return (
    <>
      <Header title={t('navCases')} subtitle="FIR Management & Search" user={user} />
      <div className="page-content" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {/* Search + Filters */}
        <div className="card" style={{ padding: '0.85rem 1rem' }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: 1, minWidth: 220 }}>
              <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
              <input
                value={q} onChange={e => { setQ(e.target.value); setOffset(0) }}
                placeholder="Search by FIR No., crime description…"
                style={{ width: '100%', paddingLeft: 30, paddingRight: 10, paddingTop: 7, paddingBottom: 7, border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.78rem', outline: 'none', fontFamily: 'inherit' }}
              />
            </div>
            {[
              { label: t('district'), value: district, setter: setDistrict, options: districts },
              { label: t('crimeType'), value: crimeType, setter: setCrimeType, options: crimeTypes },
              { label: t('status'), value: status, setter: setStatus, options: ['Under Investigation','Charge-Sheeted','Closed','FIR Filed'] },
              { label: t('date'), value: year, setter: setYear, options: ['2020','2021','2022','2023','2024'] },
            ].map(f => (
              <select key={f.label} value={f.value} onChange={e => { f.setter(e.target.value); setOffset(0) }}
                style={{ padding: '6px 10px', fontSize: '0.75rem', border: '1px solid #E2E8F0', borderRadius: 6, background: '#fff', color: '#475569', cursor: 'pointer', outline: 'none' }}>
                <option value="">{f.label}: {t('all')}</option>
                {f.options.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ))}
            {(q || district || crimeType || status || year) && (
              <button onClick={() => { setQ(''); setDistrict(''); setCrimeType(''); setStatus(''); setYear(''); setOffset(0) }}
                style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '6px 10px', fontSize: '0.72rem', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 6, cursor: 'pointer', color: '#991B1B' }}>
                <X size={11} />Clear
              </button>
            )}
            <button onClick={() => setShowUpload(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 12px', fontSize: '0.72rem', fontWeight: 600, background: '#0B1D3A', color: '#C5A028', border: 'none', borderRadius: 6, cursor: 'pointer' }}>
              <Upload size={12} />Ingest Document
            </button>
          </div>
        </div>

        {/* Count + Table */}
        <div className="card" style={{ padding: 0, overflow: 'hidden', flex: 1 }}>
          <div style={{ padding: '10px 14px', borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.75rem', color: '#64748B' }}>
              {loading ? t('loading') : `Showing ${offset + 1}–${Math.min(offset + LIMIT, total)} of ${total.toLocaleString('en-IN')} FIRs`}
            </span>
            <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>Page {currentPage} of {pages || 1}</span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t('casesFirNumber')}</th>
                  <th>{t('casesRegistrationDate')}</th>
                  <th>{t('casesDistrictPs')}</th>
                  <th>{t('casesCrimeType')}</th>
                  <th>{t('casesIpcSection')}</th>
                  <th>{t('casesStatus')}</th>
                  <th>{t('casesAccused')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j}><div style={{ height: 12, background: '#F1F5F9', borderRadius: 4, width: j === 0 ? 140 : 80 }} /></td>
                      ))}
                    </tr>
                  ))
                ) : firs.map(fir => (
                  <tr key={fir.fir_number} style={{ cursor: 'pointer' }} onClick={() => setSelectedFIR(fir)}>
                    <td><span className="fir-no mono">{fir.fir_number}</span></td>
                    <td style={{ color: '#64748B', fontSize: '0.73rem' }}>{fir.registration_date}</td>
                    <td style={{ fontSize: '0.73rem' }}>
                      <div style={{ fontWeight: 600 }}>{fir.district}</div>
                      <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>{fir.police_station}</div>
                    </td>
                    <td style={{ fontWeight: 600, fontSize: '0.75rem' }}>{fir.crime_type}</td>
                    <td><span style={{ fontFamily: 'monospace', fontSize: '0.68rem', color: '#7E22CE', background: '#F5F3FF', padding: '2px 6px', borderRadius: 3 }}>{fir.ipc_section}</span></td>
                    <td><span className={statusClass(fir.status)} style={{ fontSize: '0.62rem' }}>{fir.status?.replace('Under Investigation','Investigating')}</span></td>
                    <td style={{ fontSize: '0.75rem', textAlign: 'center' }}>{fir.accused_count || 0}</td>
                    <td>
                      <button style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 8px', fontSize: '0.65rem', border: '1px solid #E2E8F0', borderRadius: 4, background: '#F8FAFC', cursor: 'pointer', color: '#475569', whiteSpace: 'nowrap' }}>
                        <Eye size={10} />View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {pages > 1 && (
            <div style={{ padding: '10px 14px', borderTop: '1px solid #F1F5F9', display: 'flex', gap: 6, justifyContent: 'center' }}>
              <button onClick={() => setOffset(Math.max(0, offset - LIMIT))} disabled={offset === 0}
                style={{ padding: '4px 12px', fontSize: '0.72rem', border: '1px solid #E2E8F0', borderRadius: 5, background: '#fff', cursor: offset === 0 ? 'not-allowed' : 'pointer', color: '#475569' }}>
                ← Prev
              </button>
              <span style={{ fontSize: '0.72rem', color: '#64748B', padding: '4px 8px' }}>
                {currentPage} / {pages}
              </span>
              <button onClick={() => setOffset(offset + LIMIT)} disabled={offset + LIMIT >= total}
                style={{ padding: '4px 12px', fontSize: '0.72rem', border: '1px solid #E2E8F0', borderRadius: 5, background: '#fff', cursor: offset + LIMIT >= total ? 'not-allowed' : 'pointer', color: '#475569' }}>
                Next →
              </button>
            </div>
          )}
        </div>
      </div>

      {selectedFIR && <FIRModal fir={selectedFIR} onClose={() => setSelectedFIR(null)} />}
      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </>
  )
}
