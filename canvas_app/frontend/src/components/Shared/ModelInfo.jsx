import { useState, useRef, useEffect } from 'react'

export default function ModelInfo({ model, models }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const info = models?.find(m => (m.id || m) === (model || ''))
  if (!info) return null

  const contextLength = info.context_length || info.max_context || ''
  const ownedBy = info.owned_by || ''

  return (
    <div className="model-info" ref={ref}>
      <button className="model-info-trigger toolbar-btn" onClick={() => setOpen(!open)} title="Model details">
        {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="model-info-popup">
          <div className="model-info-row">
            <span className="model-info-label">Model</span>
            <span className="model-info-value">{info.name || info.id || model}</span>
          </div>
          {ownedBy && (
            <div className="model-info-row">
              <span className="model-info-label">Provider</span>
              <span className="model-info-value">{ownedBy}</span>
            </div>
          )}
          {contextLength && (
            <div className="model-info-row">
              <span className="model-info-label">Context</span>
              <span className="model-info-value">{contextLength.toLocaleString?.() || contextLength} tokens</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
