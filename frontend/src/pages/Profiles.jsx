import { useState, useEffect } from 'react'
import { searchAccused, getAccusedProfile, getIdentityConfidenceHistory } from '../services/api'
import Header from '../components/Header'
import { Search, X, AlertTriangle, Network as NetIcon, FileText, Shield, User, MapPin, Briefcase, ShieldCheck, ShieldAlert } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useLanguage } from '../i18n/LanguageContext'

const RISK_COLORS = { EXTREME: '#C0392B', HIGH: '#E67E22', MEDIUM: '#F39C12', LOW: '#27AE60' }
const RISK_BG    = { EXTREME: '#FEE2E2', HIGH: '#FEF3C7', MEDIUM: '#FEFCE8', LOW: '#D1FAE5' }

function RiskMeter({ score, category }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 600 }}>Risk Score</span>
        <span style={{ fontSize: '0.9rem', fontWeight: 800, color: RISK_COLORS[category] }}>{score}</span>
      </div>
      <div style={{ height: 6, background: '#F1F5F9', borderRadius: 9999 }}>
        <div style={{
          height: '100%', borderRadius: 9999,
          width: `${score}%`,
          background: `linear-gradient(90deg, ${RISK_COLORS['LOW']}, ${RISK_COLORS['MEDIUM']}, ${RISK_COLORS['HIGH']}, ${RISK_COLORS['EXTREME']})`,
          transition: 'width 0.8s ease',
        }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: '0.55rem', color: '#CBD5E1' }}>
        <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
      </div>
    </div>
  )
}

function ProfileModal({ accusedId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('overview')
  const [idHistory, setIdHistory] = useState(null)

  useEffect(() => {
    getAccusedProfile(accusedId)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [accusedId])

  useEffect(() => {
    if (tab === 'identity' && !idHistory) {
      getIdentityConfidenceHistory(accusedId).then(setIdHistory).catch(() => setIdHistory({ history: [] }))
    }
  }, [tab, accusedId, idHistory])

  const TABS = [
    { id: 'overview',  label: 'Overview' },
    { id: 'history',   label: `Cases (${data?.fir_history?.length || '…'})` },
    { id: 'network',   label: `Network (${data?.network_connections?.length || '…'})` },
    { id: 'risk',      label: 'Risk Assessment' },
    { id: 'identity',  label: data?.identity_confidence?.status === 'needs_review' ? '⚠ Identity' : 'Identity' },
  ]

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 1000, padding: '1rem', backdropFilter: 'blur(4px)',
    }}>
      <div style={{
        background: '#fff', borderRadius: 12,
        width: '100%', maxWidth: 720, maxHeight: '90vh',
        display: 'flex', flexDirection: 'column',
        boxShadow: '0 24px 64px rgba(0,0,0,0.25)',
        animation: 'slideUp 0.25s ease-out',
        overflow: 'hidden',
      }}>
        {loading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#94A3B8' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', border: '3px solid #E2E8F0', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
            Loading profile…
          </div>
        ) : data ? (
          <>
            {/* Profile header */}
            <div style={{
              background: 'linear-gradient(135deg, #0B1D3A 0%, #1A3360 100%)',
              padding: '1.25rem 1.5rem',
              display: 'flex', alignItems: 'flex-start', gap: 16, position: 'relative',
            }}>
              <button onClick={onClose} style={{
                position: 'absolute', top: 12, right: 12,
                background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%',
                width: 28, height: 28, cursor: 'pointer', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <X size={14} />
              </button>

              {/* Avatar */}
              <div style={{
                width: 56, height: 56, borderRadius: '50%',
                background: RISK_COLORS[data.risk_category] || '#64748B',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '1.3rem', fontWeight: 800, color: '#fff',
                border: '3px solid rgba(255,255,255,0.2)', flexShrink: 0,
              }}>
                {data.name?.[0]}
              </div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                  <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#fff' }}>{data.name}</h2>
                  {data.alias && <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)', fontStyle: 'italic' }}>"{data.alias}"</span>}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
                  <span className={`risk-badge risk-${data.risk_category}`}>{data.risk_category} RISK</span>
                  {data.is_repeat_offender === 1 && (
                    <span style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.05em', padding: '2px 8px', borderRadius: 3, background: 'rgba(192,57,43,0.3)', color: '#FCA5A5', border: '1px solid rgba(192,57,43,0.4)' }}>
                      ⚠ REPEAT OFFENDER
                    </span>
                  )}
                  {data.gang_affiliation && (
                    <span style={{ fontSize: '0.62rem', fontWeight: 700, padding: '2px 8px', borderRadius: 3, background: 'rgba(197,160,40,0.2)', color: '#C5A028', border: '1px solid rgba(197,160,40,0.3)' }}>
                      🔗 {data.gang_affiliation}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
                  {[
                    { label: 'ACC ID', value: `ACC-${String(data.accused_id).padStart(3,'0')}` },
                    { label: 'Age', value: `${data.age} yrs, ${data.gender === 'M' ? 'Male' : 'Female'}` },
                    { label: 'Prior Convictions', value: data.prior_convictions },
                    { label: 'Risk Score', value: `${data.risk_score}/100` },
                  ].map(item => (
                    <div key={item.label}>
                      <div style={{ fontSize: '0.58rem', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>{item.label}</div>
                      <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'rgba(255,255,255,0.9)', marginTop: 1 }}>{item.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', background: '#F8FAFC', flexShrink: 0 }}>
              {TABS.map(t => (
                <button key={t.id} onClick={() => setTab(t.id)} style={{
                  padding: '10px 18px', fontSize: '0.75rem', fontWeight: 600,
                  border: 'none', cursor: 'pointer',
                  background: 'none',
                  color: tab === t.id ? '#0B1D3A' : '#64748B',
                  borderBottom: `2px solid ${tab === t.id ? '#C5A028' : 'transparent'}`,
                  transition: 'all 0.15s',
                }}>
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ overflowY: 'auto', flex: 1, padding: '1.25rem 1.5rem' }}>
              {tab === 'overview' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div>
                    <div className="section-title">Personal Details</div>
                    {[
                      { icon: User,     label: 'Full Name',   value: data.name },
                      { icon: MapPin,   label: 'Address',     value: data.address },
                      { icon: MapPin,   label: 'District',    value: data.district },
                      { icon: Briefcase,label: 'Occupation',  value: data.occupation || 'N/A' },
                      { icon: Shield,   label: 'Education',   value: data.education || 'N/A' },
                    ].map(item => (
                      <div key={item.label} style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
                        <item.icon size={13} color="#94A3B8" style={{ marginTop: 2, flexShrink: 0 }} />
                        <div>
                          <div style={{ fontSize: '0.62rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 1 }}>{item.label}</div>
                          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1E293B' }}>{item.value}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="section-title">Criminal Profile</div>
                    <RiskMeter score={data.risk_score} category={data.risk_category} />
                    {data.modus_operandi && (
                      <div style={{ marginTop: 14, padding: '10px 12px', background: '#FFFBEB', borderRadius: 6, border: '1px solid #FDE68A' }}>
                        <div style={{ fontSize: '0.62rem', fontWeight: 700, color: '#92400E', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Modus Operandi</div>
                        <div style={{ fontSize: '0.75rem', color: '#78350F', lineHeight: 1.55 }}>{data.modus_operandi}</div>
                      </div>
                    )}
                    {data.is_arrested === 1 && (
                      <div style={{ marginTop: 10, padding: '8px 12px', background: '#D1FAE5', borderRadius: 5, border: '1px solid #6EE7B7', fontSize: '0.72rem', color: '#065F46', fontWeight: 600 }}>
                        ✓ Currently Arrested {data.arrest_date && `— ${data.arrest_date}`}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {tab === 'history' && (
                <div>
                  <div className="section-title">FIR History ({data.fir_history?.length || 0} cases)</div>
                  {data.fir_history?.length === 0 ? (
                    <p style={{ color: '#94A3B8', fontSize: '0.8rem' }}>No FIR history on record.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {data.fir_history?.map((f, i) => (
                        <div key={i} style={{
                          display: 'grid', gridTemplateColumns: '1fr auto auto auto',
                          gap: 12, alignItems: 'center',
                          padding: '10px 12px', background: '#F8FAFC',
                          border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.75rem',
                        }}>
                          <div>
                            <div className="mono" style={{ color: '#1D4ED8', fontWeight: 700, fontSize: '0.72rem' }}>{f.fir_number}</div>
                            <div style={{ fontWeight: 600, color: '#1E293B', marginTop: 2 }}>{f.crime_type}</div>
                            <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>{f.district} • {f.police_station}</div>
                          </div>
                          <div style={{ fontFamily: 'monospace', fontSize: '0.68rem', background: '#F5F3FF', color: '#7E22CE', padding: '2px 6px', borderRadius: 3 }}>{f.ipc_section}</div>
                          <div style={{ fontSize: '0.65rem', color: '#64748B' }}>{f.registration_date}</div>
                          <span className={`status-pill ${f.status === 'Charge-Sheeted' ? 'status-sheeted' : f.status === 'Closed' ? 'status-closed' : 'status-open'}`} style={{ fontSize: '0.6rem' }}>
                            {f.status?.replace('Under Investigation','Investing')}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'network' && (
                <div>
                  <div className="section-title">Known Associates ({data.network_connections?.length || 0})</div>
                  {data.network_connections?.length === 0 ? (
                    <p style={{ color: '#94A3B8', fontSize: '0.8rem' }}>No known criminal network connections.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {data.network_connections?.map((n, i) => (
                        <div key={i} style={{
                          display: 'flex', alignItems: 'center', gap: 12,
                          padding: '10px 12px', background: '#F8FAFC',
                          border: '1px solid #E2E8F0', borderRadius: 6,
                        }}>
                          <div style={{
                            width: 34, height: 34, borderRadius: '50%',
                            background: RISK_COLORS[n.risk_category] || '#64748B',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.75rem', fontWeight: 700, color: '#fff', flexShrink: 0,
                          }}>
                            {n.connected_name?.[0]}
                          </div>
                          <div style={{ flex: 1 }}>
                            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E293B' }}>{n.connected_name}</div>
                            <div style={{ fontSize: '0.65rem', color: '#64748B', marginTop: 1 }}>
                              {n.gang_affiliation || 'Independent'} • {n.relationship_type}
                            </div>
                          </div>
                          <div style={{ display: 'flex', flex: 'column', alignItems: 'flex-end', gap: 4 }}>
                            <span className={`risk-badge risk-${n.risk_category}`}>{n.risk_category}</span>
                            <div style={{ fontSize: '0.6rem', color: '#94A3B8', marginTop: 3, textAlign: 'right' }}>
                              Strength: {Math.round((n.strength || 0.5) * 100)}%
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div style={{ marginTop: 14 }}>
                    <a href={`/network?focus=${accusedId}`} style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      background: '#0B1D3A', color: '#C5A028', borderRadius: 6,
                      padding: '8px 16px', fontSize: '0.75rem', fontWeight: 600,
                      textDecoration: 'none',
                    }}>
                      <NetIcon size={13} />
                      Open in Network Graph
                    </a>
                  </div>
                </div>
              )}

              {tab === 'risk' && data.risk_assessment && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div style={{
                      padding: '1rem', background: RISK_BG[data.risk_assessment.category] || '#F8FAFC',
                      borderRadius: 8, border: `1px solid ${RISK_COLORS[data.risk_assessment.category]}33`,
                      textAlign: 'center',
                    }}>
                      <div style={{ fontSize: '2.5rem', fontWeight: 900, color: RISK_COLORS[data.risk_assessment.category], lineHeight: 1 }}>
                        {data.risk_assessment.score}
                      </div>
                      <div style={{ fontSize: '0.62rem', color: '#64748B', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Risk Score / 100</div>
                      <span className={`risk-badge risk-${data.risk_assessment.category}`} style={{ marginTop: 8, display: 'inline-flex' }}>
                        {data.risk_assessment.category} RISK
                      </span>
                    </div>
                    <div style={{ padding: '1rem', background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0', fontSize: '0.75rem', color: '#334155', lineHeight: 1.6 }}>
                      {data.risk_assessment.description}
                    </div>
                  </div>

                  <div className="section-title">Score Breakdown</div>
                  {Object.entries(data.risk_assessment.breakdown || {}).map(([factor, detail]) => (
                    <div key={factor} style={{ marginBottom: 14 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 5 }}>
                        <div>
                          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#1E293B' }}>{factor}</span>
                          <span style={{ fontSize: '0.65rem', color: '#94A3B8', marginLeft: 8 }}>{detail.detail}</span>
                        </div>
                        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1E293B' }}>{detail.score}/{detail.max}</span>
                      </div>
                      <div style={{ height: 8, background: '#F1F5F9', borderRadius: 9999 }}>
                        <div style={{
                          height: '100%', borderRadius: 9999,
                          width: `${(detail.score / detail.max) * 100}%`,
                          background: RISK_COLORS[data.risk_assessment.category],
                          transition: 'width 0.8s ease',
                        }} />
                      </div>
                    </div>
                  ))}

                  <div style={{
                    marginTop: 16, padding: '12px 14px',
                    background: data.risk_assessment.category === 'EXTREME' ? '#FEF2F2' : '#FFF9DB',
                    borderRadius: 8,
                    border: `1px solid ${data.risk_assessment.category === 'EXTREME' ? '#FECACA' : '#FDE68A'}`,
                  }}>
                    <div style={{ fontSize: '0.65rem', fontWeight: 700, color: data.risk_assessment.category === 'EXTREME' ? '#991B1B' : '#78350F', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      ⚡ Recommended Action
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#374151', lineHeight: 1.6 }}>
                      {data.risk_assessment.recommendation}
                    </div>
                  </div>
                </div>
              )}

              {tab === 'identity' && data.identity_confidence && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                    <div style={{
                      padding: '1rem',
                      background: data.identity_confidence.status === 'needs_review' ? '#FEF2F2' : '#F0FDF4',
                      borderRadius: 8,
                      border: `1px solid ${data.identity_confidence.status === 'needs_review' ? '#FECACA' : '#BBF7D0'}`,
                      textAlign: 'center',
                    }}>
                      <div style={{ fontSize: '2.5rem', fontWeight: 900, lineHeight: 1, color: data.identity_confidence.status === 'needs_review' ? '#C0392B' : '#166534' }}>
                        {data.identity_confidence.confidence}%
                      </div>
                      <div style={{ fontSize: '0.62rem', color: '#64748B', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Identity Confidence</div>
                      <span style={{
                        marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 4,
                        fontSize: '0.62rem', fontWeight: 700, padding: '3px 10px', borderRadius: 999,
                        background: data.identity_confidence.status === 'needs_review' ? '#FEE2E2' : '#D1FAE5',
                        color: data.identity_confidence.status === 'needs_review' ? '#991B1B' : '#065F46',
                      }}>
                        {data.identity_confidence.status === 'needs_review'
                          ? <><ShieldAlert size={11} /> NEEDS REVIEW</>
                          : <><ShieldCheck size={11} /> STABLE</>}
                      </span>
                    </div>
                    <div style={{ padding: '1rem', background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0', fontSize: '0.75rem', color: '#334155', lineHeight: 1.6 }}>
                      <div style={{ fontSize: '0.62rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Why</div>
                      {data.identity_confidence.reason}
                    </div>
                  </div>

                  <div className="section-title">Confidence Over Time ({idHistory?.history?.length || 0} snapshot{idHistory?.history?.length === 1 ? '' : 's'})</div>
                  {!idHistory ? (
                    <p style={{ color: '#94A3B8', fontSize: '0.75rem' }}>Loading history…</p>
                  ) : idHistory.history.length <= 1 ? (
                    <p style={{ color: '#94A3B8', fontSize: '0.75rem' }}>
                      Only one snapshot so far — this identity's confidence hasn't changed yet. It will move as
                      new linked case records either corroborate or contradict what's already on file.
                    </p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {idHistory.history.map((h, i) => {
                        const prev = idHistory.history[i - 1]
                        const delta = prev ? h.confidence - prev.confidence : 0
                        return (
                          <div key={i} style={{
                            display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px',
                            background: h.status === 'needs_review' ? '#FEF2F2' : '#F8FAFC',
                            border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.72rem',
                          }}>
                            <span style={{ fontWeight: 800, width: 48, color: h.status === 'needs_review' ? '#C0392B' : '#166534' }}>
                              {h.confidence}%
                            </span>
                            {i > 0 && (
                              <span style={{ fontSize: '0.65rem', color: delta >= 0 ? '#16A34A' : '#C0392B', width: 40 }}>
                                {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}
                              </span>
                            )}
                            <span style={{ flex: 1, color: '#475569' }}>{h.reason}</span>
                            <span style={{ fontSize: '0.62rem', color: '#94A3B8', flexShrink: 0 }}>{h.recorded_at?.slice(0, 16)}</span>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#C0392B' }}>
            Failed to load profile. Please try again.
          </div>
        )}
      </div>
    </div>
  )
}

function OffenderCard({ acc, onClick }) {
  return (
    <div className="offender-card" onClick={onClick} style={{ cursor: 'pointer' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
        <div className="offender-photo" style={{ background: RISK_COLORS[acc.risk_category] || '#64748B' }}>
          {acc.name?.[0]}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{acc.name}</div>
          {acc.alias && <div style={{ fontSize: '0.65rem', color: '#94A3B8', fontStyle: 'italic', marginTop: 1 }}>"{acc.alias}"</div>}
          <div style={{ display: 'flex', gap: 6, marginTop: 5, flexWrap: 'wrap' }}>
            <span className={`risk-badge risk-${acc.risk_category}`}>{acc.risk_category}</span>
            {acc.is_repeat_offender === 1 && <span style={{ fontSize: '0.58rem', fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: '#FEE2E2', color: '#991B1B', border: '1px solid #FECACA' }}>REPEAT</span>}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: RISK_COLORS[acc.risk_category] }}>{Math.round(acc.risk_score)}</div>
          <div style={{ fontSize: '0.55rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Score</div>
        </div>
      </div>

      <div style={{ height: 4, background: '#F1F5F9', borderRadius: 9999, marginBottom: 10 }}>
        <div style={{ height: '100%', borderRadius: 9999, width: `${acc.risk_score}%`, background: RISK_COLORS[acc.risk_category], transition: 'width 0.6s ease' }} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
        {[
          { label: 'Age', value: `${acc.age} yrs` },
          { label: 'Convictions', value: acc.prior_convictions },
          { label: 'District', value: acc.district },
          { label: 'Cases', value: acc.total_cases || 0 },
        ].map(item => (
          <div key={item.label} style={{ background: '#F8FAFC', borderRadius: 5, padding: '5px 8px' }}>
            <div style={{ fontSize: '0.58rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{item.label}</div>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#1E293B', marginTop: 1 }}>{item.value}</div>
          </div>
        ))}
      </div>

      {acc.gang_affiliation && (
        <div style={{ marginTop: 8, padding: '5px 8px', background: '#EFF6FF', borderRadius: 5, fontSize: '0.65rem', color: '#1D4ED8', fontWeight: 600 }}>
          🔗 {acc.gang_affiliation}
        </div>
      )}
    </div>
  )
}

export default function Profiles({ user }) {
  const { t, tv } = useLanguage()
  const [accused, setAccused] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [repeatOnly, setRepeatOnly] = useState(false)
  const [selectedId, setSelectedId] = useState(null)
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const idFromUrl = searchParams.get('id')
    if (idFromUrl) setSelectedId(parseInt(idFromUrl))
  }, [searchParams])

  useEffect(() => {
    setLoading(true)
    searchAccused({
      q: q || undefined,
      risk_category: riskFilter || undefined,
      repeat_only: repeatOnly || undefined,
      limit: 40,
    })
      .then(d => { setAccused(d.results); setTotal(d.total) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [q, riskFilter, repeatOnly])

  return (
    <>
      <Header title={t('navProfiles')} subtitle="Risk Assessment & Criminal Intelligence" user={user} />
      <div className="page-content">
        {/* Filters */}
        <div style={{ display: 'flex', gap: 8, marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
            <input
              value={q} onChange={e => setQ(e.target.value)}
              placeholder="Search by name, alias, modus operandi…"
              style={{ width: '100%', paddingLeft: 30, paddingRight: 10, paddingTop: 7, paddingBottom: 7, border: '1px solid #E2E8F0', borderRadius: 6, fontSize: '0.78rem', outline: 'none', fontFamily: 'inherit' }}
            />
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            {['', 'EXTREME', 'HIGH', 'MEDIUM', 'LOW'].map(r => (
              <button key={r} onClick={() => setRiskFilter(r)} style={{
                padding: '5px 10px', fontSize: '0.68rem', fontWeight: 600, cursor: 'pointer',
                borderRadius: 5, border: `1px solid ${riskFilter === r ? (RISK_COLORS[r] || '#0B1D3A') : '#E2E8F0'}`,
                background: riskFilter === r ? (RISK_COLORS[r] || '#0B1D3A') : '#fff',
                color: riskFilter === r ? '#fff' : '#64748B', transition: 'all 0.15s',
              }}>
                {r || t('netFilterAllRisk')}
              </button>
            ))}
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.75rem', color: '#475569', cursor: 'pointer' }}>
            <input type="checkbox" checked={repeatOnly} onChange={e => setRepeatOnly(e.target.checked)} style={{ accentColor: '#C5A028' }} />
            Repeat Offenders Only
          </label>
          <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>
            {loading ? t('loading') : `${total.toLocaleString('en-IN')} profiles`}
          </span>
        </div>

        {/* Grid */}
        {loading ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '0.75rem' }}>
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 8, padding: '1rem', height: 180 }}>
                <div style={{ display: 'flex', gap: 10, marginBottom: 10 }}>
                  <div style={{ width: 44, height: 44, borderRadius: '50%', background: '#F1F5F9' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ height: 12, background: '#F1F5F9', borderRadius: 4, width: '70%', marginBottom: 6 }} />
                    <div style={{ height: 10, background: '#F1F5F9', borderRadius: 4, width: '40%' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '0.75rem' }}>
            {accused.map(acc => (
              <OffenderCard key={acc.accused_id} acc={acc} onClick={() => setSelectedId(acc.accused_id)} />
            ))}
            {accused.length === 0 && (
              <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '3rem', color: '#94A3B8' }}>
                No offenders found matching your filters.
              </div>
            )}
          </div>
        )}
      </div>

      {selectedId && <ProfileModal accusedId={selectedId} onClose={() => setSelectedId(null)} />}
    </>
  )
}
