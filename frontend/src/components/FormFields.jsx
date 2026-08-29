/*
  Shared small form-field components used by any "review a draft before
  saving" UI in KAVACH — originally lived only inside Cases.jsx's
  UploadModal, moved here so DocumentReviewCard.jsx (the chat-with-a-PDF
  review card — see pages/CrimeChat.jsx) can render an IDENTICAL-looking
  form without duplicating ~70 lines of markup. Cases.jsx now imports
  these instead of defining them locally; behaviour is unchanged.
*/
import { Plus, Trash2 } from 'lucide-react'

const labelStyle = {
  display: 'block', fontSize: '0.62rem', color: '#94A3B8', marginBottom: 3,
  textTransform: 'uppercase', letterSpacing: '0.04em',
}

export function LabeledInput({ label, value, onChange, type = 'text', mono = false }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} style={{
        width: '100%', padding: '7px 9px', border: '1px solid #E2E8F0', borderRadius: 5,
        fontSize: '0.75rem', outline: 'none', fontFamily: mono ? 'monospace' : 'inherit', boxSizing: 'border-box',
      }} />
    </div>
  )
}

export function LabeledSelect({ label, value, onChange, options, placeholder, disabled = false }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} disabled={disabled} style={{
        width: '100%', padding: '7px 9px', border: '1px solid #E2E8F0', borderRadius: 5,
        fontSize: '0.75rem', outline: 'none', background: disabled ? '#F8FAFC' : '#fff',
        cursor: disabled ? 'not-allowed' : 'pointer', boxSizing: 'border-box',
      }}>
        <option value="">{placeholder}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  )
}

export function LabeledTextarea({ label, value, onChange }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <textarea value={value} onChange={e => onChange(e.target.value)} rows={2} style={{
        width: '100%', padding: '7px 9px', border: '1px solid #E2E8F0', borderRadius: 5,
        fontSize: '0.75rem', outline: 'none', fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box',
      }} />
    </div>
  )
}

export function PersonListEditor({ title, list, onAdd, onRemove, onChange }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{title}</span>
        <button onClick={onAdd} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: '0.65rem', padding: '3px 8px', border: '1px solid #E2E8F0', borderRadius: 4, background: '#F8FAFC', cursor: 'pointer', color: '#475569' }}>
          <Plus size={10} /> Add
        </button>
      </div>
      {list.length === 0 && <div style={{ fontSize: '0.68rem', color: '#CBD5E1', padding: '6px 0' }}>None added</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {list.map((p, i) => (
          <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input placeholder="Name" value={p.name} onChange={e => onChange(i, 'name', e.target.value)}
              style={{ flex: 2, padding: '6px 8px', border: '1px solid #E2E8F0', borderRadius: 5, fontSize: '0.72rem', outline: 'none' }} />
            <input placeholder="Age" type="number" value={p.age} onChange={e => onChange(i, 'age', e.target.value)}
              style={{ width: 60, padding: '6px 8px', border: '1px solid #E2E8F0', borderRadius: 5, fontSize: '0.72rem', outline: 'none' }} />
            <select value={p.gender} onChange={e => onChange(i, 'gender', e.target.value)}
              style={{ width: 70, padding: '6px 4px', border: '1px solid #E2E8F0', borderRadius: 5, fontSize: '0.72rem', outline: 'none' }}>
              <option value="">—</option>
              <option value="M">M</option>
              <option value="F">F</option>
              <option value="T">T</option>
            </select>
            <button onClick={() => onRemove(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#C0392B', display: 'flex', padding: 4 }}>
              <Trash2 size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
