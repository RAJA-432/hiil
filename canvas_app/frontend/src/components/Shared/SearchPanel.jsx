import { useState, useMemo, useRef, useEffect } from 'react'
import { searchMessages } from '../../api/chat'

export default function SearchPanel({ conversations, onSelectConversation, onClose, onResultClick }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const q = query.trim()
    if (!q) {
      setResults([])
      setSearched(false)
      setLoading(false)
      return
    }
    setLoading(true)
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await searchMessages(q)
        setResults(data.results || [])
      } catch {
        setResults([])
      } finally {
        setSearched(true)
        setLoading(false)
      }
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query])

  const groupedResults = useMemo(() => {
    const grouped = {}
    for (const r of results) {
      if (!grouped[r.conversation_id]) {
        grouped[r.conversation_id] = {
          conversation_id: r.conversation_id,
          conversation_title: r.conversation_title,
          messages: [],
        }
      }
      grouped[r.conversation_id].messages.push(r)
    }
    return Object.values(grouped)
  }, [results])

  const handleResultClick = (convId, title, messageId) => {
    const conv = conversations.find(c => c.id === convId)
    if (conv && onResultClick) {
      onResultClick(conv, messageId)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') onClose?.()
  }

  const highlightMatch = (text, q) => {
    if (!q.trim()) return text
    const idx = text.toLowerCase().indexOf(q.toLowerCase())
    if (idx === -1) return text
    const before = text.slice(0, idx)
    const match = text.slice(idx, idx + q.length)
    const after = text.slice(idx + q.length)
    return (
      <>{before}<strong>{match}</strong>{after}</>
    )
  }

  return (
    <div className="search-panel">
      <div className="search-panel-input-row">
        <input
          ref={inputRef}
          type="text"
          className="search-panel-input"
          placeholder="Search message content..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <span className="search-panel-count">
          {loading ? '…' : query.trim() ? `${results.length} result${results.length !== 1 ? 's' : ''}` : ''}
        </span>
        <button className="toolbar-btn" onClick={onClose}>✕</button>
      </div>
      <div className="search-panel-filters">
        <span className="search-panel-filter-hint">Search by message content</span>
      </div>

      {loading && (
        <div className="search-panel-loading">
          <span className="search-spinner" />
        </div>
      )}

      {!loading && groupedResults.length > 0 && (
        <div className="search-panel-results">
          {groupedResults.map(group => (
            <div key={group.conversation_id} className="search-result-group">
              <div className="search-result-conv-header">
                {group.conversation_title}
              </div>
              {group.messages.map(r => (
                <div
                  key={r.message_id}
                  className="search-result-item"
                  onClick={() => handleResultClick(r.conversation_id, r.conversation_title, r.message_id)}
                >
                  <div className="search-result-snippet">
                    {highlightMatch(r.snippet, query.trim())}
                  </div>
                  <div className="search-result-meta">
                    <span className="search-result-timestamp">
                      {new Date(r.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="search-panel-empty">No results found</div>
      )}
    </div>
  )
}
