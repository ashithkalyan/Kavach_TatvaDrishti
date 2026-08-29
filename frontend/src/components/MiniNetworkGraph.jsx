import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'

/**
 * A small, STATIC network snapshot rendered inline inside a chat
 * message — deliberately not the interactive explorer the Network page
 * is (no zoom, no pan, no drag). This is meant to be a quick "here's
 * who this person connects to" visual next to the AI's answer, not a
 * tool to investigate with — for that, the officer still has the full
 * Criminal Network page.
 */
const RISK_COLORS = { EXTREME: '#C0392B', HIGH: '#E67E22', MEDIUM: '#F39C12', LOW: '#0F7A5A' }

export default function MiniNetworkGraph({ snapshot, label = 'Connected network' }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !snapshot?.nodes?.length) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...snapshot.nodes, ...snapshot.edges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele) => RISK_COLORS[ele.data('risk')] || '#64748B',
            'label': 'data(label)',
            'font-size': 7,
            'color': '#334155',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 4,
            'width': (ele) => (ele.data('is_center') ? 24 : 16),
            'height': (ele) => (ele.data('is_center') ? 24 : 16),
            'border-width': (ele) => (ele.data('is_center') ? 2.5 : 0),
            'border-color': '#C5A028',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1.4,
            'line-color': '#CBD5E1',
            'curve-style': 'haystack',
            'haystack-radius': 0.3,
          },
        },
      ],
      layout: { name: 'cose', animate: false, fit: true, padding: 14 },
      // Deliberately static — this is a glance-and-move-on visual inside
      // a chat bubble, not an exploration tool.
      userZoomingEnabled: false,
      userPanningEnabled: false,
      boxSelectionEnabled: false,
      autoungrabify: true,
      autounselectify: true,
      minZoom: 1,
      maxZoom: 1,
    })
    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [snapshot])

  if (!snapshot?.nodes?.length) return null

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: '0.65rem', color: '#94A3B8', marginBottom: 4, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
        <span>🕸️</span> {label}
      </div>
      <div
        ref={containerRef}
        style={{
          width: '100%', maxWidth: 300, height: 140,
          background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 6,
        }}
      />
    </div>
  )
}
