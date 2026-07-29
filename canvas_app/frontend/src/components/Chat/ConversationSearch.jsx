import { useState, useMemo, useRef, useEffect } from 'react'
import MarkdownRenderer from './MarkdownRenderer'

export default function ConversationSearch({ messages, onClose }) {
  const [query, setQuery] = useState('')
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const results = useMemo(() => {
    if (!query.trim() || !messages) return []
    const q = query.toLowerCase()
    const found = []
    for (let i = 0; i < messages.length; i++) {
      const m = messages[i]
      const content = (m.content || '').toLowerCase()
      let idx = 0
      while ((idx = content.indexOf(q, idx)) !== -1) {
        found.push({
          msgIdx: i,
          role: m.role,
          start: Math.max(0, idx - 30),
          end: Math.min(content.length, idx + q.length + 60),
          preview: (m.content || '').slice(Math.max(0, idx - 30), Math.min(content.length, idx + q.length + 60)),
        })
        idx += q.length
      }
    }
    return found
  }, [query, messages])

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIdx(prev => Math.min(prev + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIdx(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Escape') {
      onClose?.()
    }
  }

  return (
    <div className="conversation-search">
      <div className="conversation-search-input-row">
        <input
          ref={inputRef}
          type="text"
          className="conversation-search-input"
          placeholder="Search in conversation…"
          aria-label="Search in conversation"
          value={query}
          onChange={e => { setQuery(e.target.value); setSelectedIdx(0) }}
          onKeyDown={handleKeyDown}
        />
        <span className="conversation-search-count">
          {query.trim() ? `${results.length} result${results.length !== 1 ? 's' : ''}` : ''}
        </span>
        <button className="toolbar-btn" onClick={onClose} aria-label="Close search">✕</button>
      </div>
      {results.length > 0 && (
        <div className="conversation-search-results">
          {results.map((r, i) => (
            <div
              key={i}
              className={`conversation-search-item ${i === selectedIdx ? 'selected' : ''}`}
              onMouseEnter={() => setSelectedIdx(i)}
            >
              <div className="conversation-search-role">{r.role}</div>
              <div className="conversation-search-preview"><MarkdownRenderer content={r.preview} /></div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
