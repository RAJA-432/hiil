import { useState } from 'react'

export default function RetrievedChunksPanel({ chunks }) {
  const [collapsed, setCollapsed] = useState(false)

  if (!chunks || chunks.length === 0) return null

  return (
    <div className="rag-chunks-panel">
      <div className="rag-chunks-header" onClick={() => setCollapsed(!collapsed)} role="button" tabIndex={0} aria-expanded={!collapsed} aria-label="Retrieved chunks" onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCollapsed(!collapsed) } }}>
        <span className="rag-chunks-icon" aria-hidden="true">📚</span>
        <span>Retrieved {chunks.length} chunk{chunks.length > 1 ? 's' : ''}</span>
        <span className="rag-chunks-toggle">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="rag-chunks-list">
          {chunks.map((chunk, i) => (
            <div className="rag-chunk-item" key={i}>
              <div className="rag-chunk-meta">
                <span className="rag-chunk-source">{chunk.metadata?.filename || 'source'}</span>
                <span className="rag-chunk-score" title="Relevance score">
                  <span className="rag-chunk-score-bar" style={{ width: `${Math.round((chunk.score || 0) * 100)}%` }} />
                  <span className="rag-chunk-score-text">{Math.round((chunk.score || 0) * 100)}%</span>
                </span>
              </div>
              <div className="rag-chunk-text">{chunk.text}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
