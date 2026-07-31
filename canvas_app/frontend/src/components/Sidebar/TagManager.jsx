import { useState, useRef, useEffect } from 'react'

const TAG_COLORS = ['#34d399', '#60a5fa', '#a78bfa', '#fbbf24', '#f87171', '#fb923c', '#e879f9', '#22d3ee']

export default function TagManager({ conversationId, tags, onAddTag, onRemoveTag }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleAdd = () => {
    if (input.trim()) {
      onAddTag(conversationId, input.trim())
      setInput('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleAdd()
    if (e.key === 'Escape') setOpen(false)
  }

  return (
    <div className="tag-manager" ref={ref}>
      <div className="tag-list">
        {(tags || []).map((tag, i) => (
          <span key={tag} className="tag" style={{ background: TAG_COLORS[i % TAG_COLORS.length] + '25', color: TAG_COLORS[i % TAG_COLORS.length] }}>
            {tag}
            <button className="tag-remove" onClick={() => onRemoveTag(conversationId, tag)}>✕</button>
          </span>
        ))}
        <button className="tag-add-btn" onClick={() => setOpen(!open)} aria-label="Add tag">+</button>
      </div>
      {open && (
        <div className="tag-input-popup">
          <input
            className="tag-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add tag..."
            autoFocus
          />
        </div>
      )}
    </div>
  )
}
