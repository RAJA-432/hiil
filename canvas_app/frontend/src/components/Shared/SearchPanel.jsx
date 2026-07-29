import { useState, useMemo, useRef, useEffect } from 'react'

export default function SearchPanel({ conversations, onSelectConversation, onClose }) {
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const results = useMemo(() => {
    if (!query.trim()) return []
    const q = query.toLowerCase()
    const matched = []
    for (const conv of conversations) {
      let score = 0
      const title = (conv.title || '').toLowerCase()
      if (title.includes(q)) score += 3
      const snippet = title.includes(q) ? conv.title : ''
      if (score > 0) {
        matched.push({ conv, score, snippet, matchType: 'title' })
      }
    }
    matched.sort((a, b) => b.score - a.score)
    return matched.slice(0, 30)
  }, [query, conversations])

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose?.()
  }

  return (
    <div className="search-panel">
      <div className="search-panel-input-row">
        <input
          ref={inputRef}
          type="text"
          className="search-panel-input"
          placeholder="Search all conversations..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <span className="search-panel-count">
          {query.trim() ? `${results.length} result${results.length !== 1 ? 's' : ''}` : ''}
        </span>
        <button className="toolbar-btn" onClick={onClose}>✕</button>
      </div>
      <div className="search-panel-filters">
        <span className="search-panel-filter-hint">Search by conversation title</span>
      </div>
      {results.length > 0 && (
        <div className="search-panel-results">
          {results.map(r => (
            <div
              key={r.conv.id}
              className="search-result-item"
              onClick={() => onSelectConversation(r.conv)}
            >
              <div className="search-result-title">{r.conv.title}</div>
              <div className="search-result-meta">{r.conv.message_count || 0} messages</div>
            </div>
          ))}
        </div>
      )}
      {query.trim() && results.length === 0 && (
        <div className="search-panel-empty">No conversations found</div>
      )}
    </div>
  )
}
