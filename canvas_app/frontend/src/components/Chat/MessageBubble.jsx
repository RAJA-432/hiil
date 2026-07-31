import { useState, useCallback, useRef, useEffect } from 'react'
import KaryaCall from './KaryaCall'
import MessageActions from './MessageActions'
import MessageTimestamp from './MessageTimestamp'
import InlineChart from './InlineChart'
import MarkdownRenderer from './MarkdownRenderer'
import { sendFeedback } from '../../api/chat'

export default function MessageBubble({ message, onOpenFile, onRetry, onDelete, onCopy, onEdit }) {
  const { role, content, tool_calls: toolCalls, timestamp, id } = message
  const [rating, setRating] = useState(0)
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(content || '')
  const editRef = useRef(null)

  useEffect(() => {
    if (editing && editRef.current) {
      editRef.current.focus()
      editRef.current.selectionStart = editRef.current.value.length
      editRef.current.selectionEnd = editRef.current.value.length
    }
  }, [editing])

  const handleDelegate = useCallback((e) => {
    const link = e.target.closest('a[data-file]')
    if (link) {
      e.preventDefault()
      onOpenFile?.(link.dataset.file)
      return
    }
    const copyBtn = e.target.closest('[data-copy]')
    if (copyBtn) {
      const code = decodeURIComponent(copyBtn.dataset.copy)
      navigator.clipboard.writeText(code).then(() => {
        copyBtn.textContent = 'Copied!'
        setTimeout(() => { copyBtn.textContent = 'Copy' }, 2000)
      }).catch(() => {})
    }
  }, [onOpenFile])

  const handleFeedback = useCallback((value) => {
    const next = rating === value ? 0 : value
    setRating(next)
    const sessionId = id || 'default'
    sendFeedback(sessionId, next, { message_id: sessionId, was_helpful: next === 1 })
  }, [rating, id])

  const handleStartEdit = useCallback(() => {
    setEditValue(content || '')
    setEditing(true)
  }, [content])

  const handleSaveEdit = useCallback(() => {
    const trimmed = editValue.trim()
    if (trimmed && trimmed !== content) {
      onEdit?.(message, trimmed)
    }
    setEditing(false)
  }, [editValue, content, message, onEdit])

  const handleCancelEdit = useCallback(() => {
    setEditing(false)
    setEditValue(content || '')
  }, [content])

  const handleEditKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault()
      handleSaveEdit()
    }
    if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }, [handleSaveEdit, handleCancelEdit])

  if (editing) {
    return (
      <div id={message.id ? `msg-${message.id}` : undefined} className={`message ${role} message-editing`}>
        <div className="message-edit-container">
          <textarea
            ref={editRef}
            className="message-edit-textarea"
            value={editValue}
            onChange={e => setEditValue(e.target.value)}
            onKeyDown={handleEditKeyDown}
            rows={Math.max(3, (editValue.match(/\n/g)?.length || 0) + 2)}
          />
          <div className="message-edit-actions">
            <span className="message-edit-hint">Ctrl+Enter to save • Escape to cancel</span>
            <button className="toolbar-btn" onClick={handleCancelEdit}>Cancel</button>
            <button className="settings-save-btn" onClick={handleSaveEdit}>Save & Re-run</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div id={message.id ? `msg-${message.id}` : undefined} className={`message ${role}`}>
      <div className="message-content" onClick={handleDelegate}>
        {role === 'assistant' ? (
          <MarkdownRenderer content={content} />
        ) : (
          content
        )}
      </div>

      {role === 'assistant' && <InlineChart text={content} />}

      <div className="message-meta">
        <MessageTimestamp timestamp={timestamp} />
        {role === 'assistant' && (
          <div className="feedback-buttons">
            <button
              className={`feedback-btn ${rating === 1 ? 'feedback-active' : ''}`}
              onClick={() => handleFeedback(1)}
              aria-label="Like this response"
              title="Helpful"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill={rating === 1 ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
              </svg>
            </button>
            <button
              className={`feedback-btn ${rating === -1 ? 'feedback-active' : ''}`}
              onClick={() => handleFeedback(-1)}
              aria-label="Dislike this response"
              title="Not helpful"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill={rating === -1 ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
              </svg>
            </button>
          </div>
        )}
        <MessageActions
          message={message}
          onRetry={onRetry}
          onDelete={onDelete}
          onCopy={onCopy}
          onEdit={role === 'user' ? handleStartEdit : undefined}
        />
      </div>

      {toolCalls?.length > 0 && (
        <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {toolCalls.map((tc, i) => (
            <KaryaCall key={i} toolCall={tc} onOpenFile={onOpenFile} />
          ))}
        </div>
      )}
    </div>
  )
}
