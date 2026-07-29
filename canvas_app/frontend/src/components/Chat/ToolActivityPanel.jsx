import { useState, useRef, useEffect } from 'react'

const LEVEL_ICON = {
  info: 'ℹ️',
  warn: '⚠️',
  error: '❌',
  tool: '🔧',
}

export default function ToolActivityPanel({ logs, ragChunks }) {
  const [filter, setFilter] = useState('all')
  const [collapsed, setCollapsed] = useState(false)
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [logs, ragChunks])

  const allEntries = [
    ...(ragChunks || []).map(c => ({
      type: 'rag',
      level: 'info',
      text: `Retrieved chunk: ${(c.text || '').slice(0, 80)}...`,
      source: 'rag',
      timestamp: Date.now(),
    })),
    ...(logs || []),
  ].sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))

  const filtered = filter === 'all'
    ? allEntries
    : allEntries.filter(e => e.level === filter || e.source === filter)

  if (allEntries.length === 0) return null

  return (
    <div className="activity-panel">
      <div className="activity-panel-header" onClick={() => setCollapsed(!collapsed)} role="button" tabIndex={0} aria-expanded={!collapsed} aria-label="Activity log" onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCollapsed(!collapsed) } }}>
        <span className="activity-panel-icon" aria-hidden="true">📋</span>
        <span>Activity Log</span>
        <span className="activity-panel-count">{allEntries.length}</span>
        <span className="activity-panel-toggle">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <>
          <div className="activity-panel-filters">
            {['all', 'info', 'tool', 'rag', 'warn', 'error'].map(f => (
              <button
                key={f}
                className={`activity-filter-btn ${filter === f ? 'active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {LEVEL_ICON[f] || ''} {f}
              </button>
            ))}
          </div>
          <div className="activity-panel-list" ref={listRef}>
            {filtered.map((entry, i) => (
              <div className={`activity-entry activity-entry-${entry.level || 'info'}`} key={i}>
                <span className="activity-entry-icon">{LEVEL_ICON[entry.level] || '📄'}</span>
                <span className="activity-entry-text">{entry.text}</span>
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="activity-entry activity-entry-empty">No matching entries</div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
