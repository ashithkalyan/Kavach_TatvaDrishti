import { useState, useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import coseBilkent from 'cytoscape-cose-bilkent'
cytoscape.use(coseBilkent)
import { getFullNetworkGraph, getGangs, getAccusedProfile } from '../services/api'
import Header from '../components/Header'
import { Users, AlertTriangle, Network as NetworkIcon, Info, X, ExternalLink } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext'

const RISK_COLORS = {
  EXTREME: '#C0392B',
  HIGH: '#E67E22',
  MEDIUM: '#F39C12',
  LOW: '#27AE60',
}

const GANG_COLORS = [
  '#6366F1', '#EC4899', '#14B8A6', '#F59E0B', '#8B5CF6', '#EF4444',
]

export default function Network({ user }) {
  const { t } = useLanguage()
  const cyRef = useRef(null)
  const containerRef = useRef(null)
  const [graphData, setGraphData] = useState(null)
  const [gangs, setGangs] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedNode, setSelectedNode] = useState(null)
  const [profileData, setProfileData] = useState(null)
  const [colorMode, setColorMode] = useState('risk') // 'risk' | 'gang'
  const [filterRisk, setFilterRisk] = useState('ALL')
  const [filterGang, setFilterGang] = useState('ALL')
  // Mirrors colorMode so the cytoscape style-mapper functions (captured once,
  // at instance-build time) can read the *current* value without colorMode
  // needing to be a dependency of the build effect below.
  const colorModeRef = useRef(colorMode)

  // Fetch data only once on mount — no dependency on any state
  useEffect(() => {
    let cancelled = false
    Promise.all([getFullNetworkGraph(100), getGangs()])
      .then(([g, gs]) => {
        if (!cancelled) {
          setGraphData(g)
          setGangs(gs.gangs || [])
        }
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // Build & render the Cytoscape graph whenever data or filters change
  useEffect(() => {
    if (!graphData || !containerRef.current) return

    // Destroy previous instance cleanly
    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    // ── Filter nodes & edges ──
    let nodes = graphData.nodes || []
    if (filterRisk !== 'ALL') nodes = nodes.filter(n => n.data.risk === filterRisk)
    const nodeIds = new Set(nodes.map(n => n.data.id))
    let edges = (graphData.edges || []).filter(e => nodeIds.has(e.data.source) && nodeIds.has(e.data.target))
    if (filterGang !== 'ALL') {
      const gIds = new Set(nodes.filter(n => n.data.gang === filterGang).map(n => n.data.id))
      edges = edges.filter(e => gIds.has(e.data.source) || gIds.has(e.data.target))
    }

    // Nothing to render
    if (nodes.length === 0) return

    const gangList = [...new Set((graphData.nodes || []).map(n => n.data.gang).filter(Boolean))]

    const cy = cytoscape({
      container: containerRef.current,
      elements: { nodes, edges },
      minZoom: 0.15,
      maxZoom: 2.5,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': n => {
              if (colorModeRef.current === 'risk') {
                return RISK_COLORS[n.data('risk')] || '#64748B'
              }
              const gi = gangList.indexOf(n.data('gang'))
              return gi >= 0 ? GANG_COLORS[gi % GANG_COLORS.length] : '#64748B'
            },
            'label': 'data(label)',
            'color': '#fff',
            'font-size': 8,
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-outline-color': '#05101F',
            'text-outline-width': 2,
            'width': n => Math.max(18, Math.min(40, 14 + (n.data('risk_score') || 0) / 4)),
            'height': n => Math.max(18, Math.min(40, 14 + (n.data('risk_score') || 0) / 4)),
            'border-width': 1.5,
            'border-color': '#fff',
            'border-opacity': 0.3,
          }
        },
        {
          selector: 'node:selected, node.highlighted',
          style: {
            'border-width': 3,
            'border-color': '#C5A028',
            'border-opacity': 1,
          }
        },
        {
          selector: 'edge',
          style: {
            'width': e => Math.max(0.8, (e.data('strength') || 0.5) * 3),
            'line-color': e => {
              const rel = e.data('relationship')
              if (rel === 'Gang Member') return '#C5A028'
              if (rel === 'Co-Accused') return '#E67E22'
              if (rel === 'Family Member') return '#EC4899'
              return '#334155'
            },
            'opacity': 0.65,
            'curve-style': 'bezier',
            'target-arrow-shape': 'none',
          }
        },
        {
          selector: 'edge:selected',
          style: { 'opacity': 1, 'width': 3 }
        },
      ],
      layout: {
        name: 'cose-bilkent',
        animate: true,
        animationDuration: 800,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
        randomize: true,
        fit: true,
        padding: 40
      }
    })

    // ── Event handlers ──
    cy.on('tap', 'node', async e => {
      cy.$('node').removeClass('highlighted')
      e.target.addClass('highlighted')
      const data = e.target.data()
      setSelectedNode(data)
      setProfileData(null)
      try {
        const profile = await getAccusedProfile(parseInt(data.id))
        setProfileData(profile)
      } catch { }
    })

    cy.on('tap', e => {
      if (e.target === cy) { setSelectedNode(null); setProfileData(null) }
    })

    cyRef.current = cy

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }
    }
  }, [graphData, filterRisk, filterGang])

  // Recolor in place when colorMode changes — no destroy, no re-layout.
  // The node style above reads colorModeRef.current, so updating the ref
  // and asking Cytoscape to re-run the style mappers is enough to repaint
  // every node at its existing position.
  useEffect(() => {
    colorModeRef.current = colorMode
    if (cyRef.current) {
      cyRef.current.style().update()
    }
  }, [colorMode])

  // Handle container resize when side-panel appears/disappears
  useEffect(() => {
    const timer = setTimeout(() => {
      if (cyRef.current) {
        cyRef.current.resize()
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [selectedNode])

  const RISK_LABELS = ['ALL', 'EXTREME', 'HIGH', 'MEDIUM', 'LOW']

  if (loading) return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ textAlign: 'center', color: '#64748B' }}>
        <div style={{ width: 36, height: 36, borderRadius: '50%', border: '3px solid #E2E8F0', borderTopColor: '#C5A028', animation: 'spin 0.8s linear infinite', margin: '0 auto 12px' }} />
        {t('netLoading')}
      </div>
    </div>
  )

  return (
    <>
      <Header title={t('netTitle')} user={user} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: '0.75rem', gap: '0.75rem' }}>
        {/* Controls bar */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', flexShrink: 0 }}>
          {/* Stats pills */}
          <div style={{ display: 'flex', gap: 8 }}>
            {[
              { icon: NetworkIcon, label: t('netNodes'), value: graphData?.total_nodes },
              { icon: Users, label: t('netConnections'), value: graphData?.edges.length },
              { icon: AlertTriangle, label: t('netGangList'), value: gangs.length },
            ].map(s => (
              <div key={s.label} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: '#0B1D3A', borderRadius: 6, padding: '5px 12px',
              }}>
                <s.icon size={12} color="#C5A028" />
                <span style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)' }}>{s.label}:</span>
                <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#C5A028' }}>{s.value}</span>
              </div>
            ))}
          </div>

          <div style={{ flex: 1 }} />

          {/* Color mode */}
          <div style={{ display: 'flex', gap: 0, border: '1px solid #E2E8F0', borderRadius: 6, overflow: 'hidden' }}>
            {['risk', 'gang'].map(m => (
              <button key={m} onClick={() => setColorMode(m)} style={{
                padding: '5px 12px', fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer', border: 'none',
                background: colorMode === m ? '#0B1D3A' : '#fff',
                color: colorMode === m ? '#C5A028' : '#64748B',
                textTransform: 'capitalize',
              }}>
                {m === 'risk' ? t('netColorByRisk') : t('netColorByGang')}
              </button>
            ))}
          </div>

          {/* Risk filter */}
          <div style={{ display: 'flex', gap: 4 }}>
            {RISK_LABELS.map(r => (
              <button key={r} onClick={() => setFilterRisk(r)} style={{
                padding: '4px 9px', fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer',
                borderRadius: 4, border: `1px solid ${filterRisk === r ? (RISK_COLORS[r] || '#0B1D3A') : '#E2E8F0'}`,
                background: filterRisk === r ? (RISK_COLORS[r] || '#0B1D3A') : '#fff',
                color: filterRisk === r ? '#fff' : '#64748B',
                transition: 'all 0.15s',
              }}>
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Main graph area */}
        <div style={{ flex: 1, display: 'flex', gap: '0.75rem', minHeight: 0 }}>
          {/* Graph */}
          <div style={{
            flex: 1, background: '#05101F', borderRadius: 10,
            border: '1px solid rgba(197,160,40,0.15)',
            position: 'relative', overflow: 'hidden',
          }}>
            <div
              ref={containerRef}
              style={{
                width: '100%',
                height: '100%'
              }}
            />

            {/* Legend */}
            <div style={{
              position: 'absolute', bottom: 14, left: 14,
              background: 'rgba(5,16,31,0.92)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 8, padding: '10px 14px',
              backdropFilter: 'blur(8px)',
            }}>
              <div style={{ fontSize: '0.62rem', color: 'rgba(255,255,255,0.4)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                {colorMode === 'risk' ? 'Risk Level' : 'Gang'}
              </div>
              {colorMode === 'risk' ? (
                Object.entries(RISK_COLORS).map(([r, c]) => (
                  <div key={r} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />
                    <span style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.7)', fontWeight: 600 }}>{r}</span>
                  </div>
                ))
              ) : (
                gangs.slice(0, 5).map((g, i) => (
                  <div key={g.name} style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: GANG_COLORS[i % GANG_COLORS.length] }} />
                    <span style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.7)' }}>{g.name}</span>
                  </div>
                ))
              )}
              <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 4 }}>
                  <div style={{ width: 20, height: 2, background: '#C5A028' }} />
                  <span style={{ fontSize: '0.62rem', color: 'rgba(255,255,255,0.4)' }}>Gang Member</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <div style={{ width: 20, height: 2, background: '#334155' }} />
                  <span style={{ fontSize: '0.62rem', color: 'rgba(255,255,255,0.4)' }}>Associate</span>
                </div>
              </div>
            </div>

            {/* Manual Zoom Controls */}
            <div style={{
              position: 'absolute', top: 14, right: 14,
              display: 'flex', flexDirection: 'column', gap: 6,
              background: 'rgba(5,16,31,0.92)', border: '1px solid rgba(197,160,40,0.3)',
              borderRadius: 8, padding: 6,
              backdropFilter: 'blur(8px)', zIndex: 10
            }}>
              <button
                onClick={() => { if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 1.25) }}
                style={{ width: 28, height: 28, background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, color: '#fff', fontSize: '1.2rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                title="Zoom In"
              >+</button>
              <button
                onClick={() => { if (cyRef.current) cyRef.current.zoom(cyRef.current.zoom() * 0.8) }}
                style={{ width: 28, height: 28, background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, color: '#fff', fontSize: '1.2rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                title="Zoom Out"
              >-</button>
              <button
                onClick={() => { if (cyRef.current) cyRef.current.fit(undefined, 50) }}
                style={{ width: 28, height: 28, background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, color: '#C5A028', fontSize: '0.9rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 4 }}
                title="Fit to Screen"
              >⛶</button>
            </div>

            {/* Instruction */}
            {!selectedNode && (
              <div style={{
                position: 'absolute', top: 14, left: '50%', transform: 'translateX(-50%)',
                background: 'rgba(197,160,40,0.12)', border: '1px solid rgba(197,160,40,0.25)',
                borderRadius: 6, padding: '6px 14px',
                fontSize: '0.68rem', color: 'rgba(255,255,255,0.6)',
                backdropFilter: 'blur(4px)', whiteSpace: 'nowrap', zIndex: 1
              }}>
                <Info size={11} style={{ display: 'inline', marginRight: 5 }} />
                Click any node to view the offender profile
              </div>
            )}
          </div>

          {/* Side panel — selected node profile */}
          {selectedNode && (
            <div style={{
              width: 280, background: '#fff', borderRadius: 10,
              border: '1px solid #E2E8F0', overflow: 'hidden',
              display: 'flex', flexDirection: 'column',
              animation: 'slideUp 0.25s ease-out', flexShrink: 0,
            }}>
              <div style={{ background: '#0B1D3A', padding: '14px 14px 12px', position: 'relative' }}>
                <button onClick={() => { setSelectedNode(null); setProfileData(null) }} style={{
                  position: 'absolute', top: 8, right: 8,
                  background: 'rgba(255,255,255,0.1)', border: 'none', borderRadius: '50%',
                  width: 22, height: 22, cursor: 'pointer', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <X size={12} />
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: '50%',
                    background: RISK_COLORS[selectedNode.risk] || '#64748B',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '0.85rem', fontWeight: 700, color: '#fff',
                  }}>
                    {selectedNode.label?.[0]}
                  </div>
                  <div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#fff' }}>{selectedNode.label}</div>
                    <div style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>
                      ACC-{selectedNode.id?.toString().padStart(3, '0')}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                  <span className={`risk-badge risk-${selectedNode.risk}`}>{selectedNode.risk}</span>
                  <span style={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center' }}>
                    Score: {selectedNode.risk_score?.toFixed(1)}/100
                  </span>
                </div>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px' }}>
                {[
                  { label: 'Gang', value: selectedNode.gang || 'Independent' },
                  { label: 'Prior Convictions', value: selectedNode.convictions },
                  { label: 'Total Cases', value: selectedNode.cases },
                ].map(item => (
                  <div key={item.label} style={{
                    display: 'flex', justifyContent: 'space-between',
                    padding: '7px 0', borderBottom: '1px solid #F1F5F9', fontSize: '0.75rem',
                  }}>
                    <span style={{ color: '#64748B' }}>{item.label}</span>
                    <span style={{ fontWeight: 600, color: '#1E293B', textAlign: 'right', maxWidth: '55%' }}>{item.value}</span>
                  </div>
                ))}

                {profileData && (
                  <>
                    {[
                      { label: 'Age', value: profileData.age },
                      { label: 'District', value: profileData.district },
                      { label: 'Occupation', value: profileData.occupation },
                    ].map(item => (
                      <div key={item.label} style={{
                        display: 'flex', justifyContent: 'space-between',
                        padding: '7px 0', borderBottom: '1px solid #F1F5F9', fontSize: '0.75rem',
                      }}>
                        <span style={{ color: '#64748B' }}>{item.label}</span>
                        <span style={{ fontWeight: 600, color: '#1E293B' }}>{item.value}</span>
                      </div>
                    ))}
                    {profileData.modus_operandi && (
                      <div style={{ marginTop: 10, padding: '8px 10px', background: '#FFF9DB', borderRadius: 5, fontSize: '0.7rem', color: '#78350F' }}>
                        <div style={{ fontWeight: 700, marginBottom: 4 }}>Modus Operandi</div>
                        {profileData.modus_operandi}
                      </div>
                    )}
                    {profileData.risk_assessment && (
                      <div style={{ marginTop: 10 }}>
                        <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#64748B', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Risk Breakdown</div>
                        {Object.entries(profileData.risk_assessment.breakdown || {}).map(([factor, data]) => (
                          <div key={factor} style={{ marginBottom: 8 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', marginBottom: 3 }}>
                              <span style={{ color: '#475569' }}>{factor}</span>
                              <span style={{ fontWeight: 600 }}>{data.score}/{data.max}</span>
                            </div>
                            <div style={{ height: 5, background: '#F1F5F9', borderRadius: 9999 }}>
                              <div style={{
                                height: '100%', borderRadius: 9999,
                                width: `${(data.score / data.max) * 100}%`,
                                background: RISK_COLORS[selectedNode.risk] || '#64748B',
                                transition: 'width 0.6s ease',
                              }} />
                            </div>
                          </div>
                        ))}
                        <div style={{ marginTop: 8, padding: '8px 10px', background: '#FEF2F2', borderRadius: 5, fontSize: '0.68rem', color: '#7F1D1D' }}>
                          {profileData.risk_assessment.recommendation}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>

              <div style={{ padding: '10px 14px', borderTop: '1px solid #E2E8F0', background: '#F8FAFC' }}>
                <a
                  href={`/profiles?id=${selectedNode.id}`}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    background: '#0B1D3A', color: '#C5A028', borderRadius: 6,
                    padding: '7px', fontSize: '0.72rem', fontWeight: 600,
                    textDecoration: 'none', transition: 'all 0.15s',
                  }}
                >
                  <ExternalLink size={11} />
                  Full Profile & Case History
                </a>
              </div>
            </div>
          )}

          {/* Gang list */}
          {!selectedNode && (
            <div style={{
              width: 220, display: 'flex', flexDirection: 'column', gap: 8, flexShrink: 0,
            }}>
              <div style={{ fontSize: '0.68rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em', flexShrink: 0 }}>
                Known Gangs
              </div>
              {gangs.map((g, i) => (
                <div key={g.name} style={{
                  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 8,
                  padding: '10px 12px', animation: 'fadeIn 0.3s ease-out',
                  borderLeft: `3px solid ${GANG_COLORS[i % GANG_COLORS.length]}`,
                  cursor: 'pointer',
                }}
                  onClick={() => setFilterGang(filterGang === g.name ? 'ALL' : g.name)}
                >
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#1E293B', marginBottom: 6 }}>{g.name}</div>
                  <div style={{ display: 'flex', gap: 10, fontSize: '0.65rem' }}>
                    <div>
                      <div style={{ color: '#94A3B8' }}>Members</div>
                      <div style={{ fontWeight: 700, color: '#1E293B' }}>{g.member_count}</div>
                    </div>
                    <div>
                      <div style={{ color: '#94A3B8' }}>Avg Risk</div>
                      <div style={{ fontWeight: 700, color: RISK_COLORS[g.avg_risk >= 80 ? 'EXTREME' : g.avg_risk >= 60 ? 'HIGH' : 'MEDIUM'] }}>
                        {g.avg_risk?.toFixed(0)}
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: '0.6rem', color: '#94A3B8', marginTop: 4 }}>
                    {g.districts?.split(',').slice(0, 2).join(', ')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
