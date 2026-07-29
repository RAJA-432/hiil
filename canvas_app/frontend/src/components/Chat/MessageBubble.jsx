import { useState, useCallback, useRef, useEffect } from 'react'
import KaryaCall from './KaryaCall'
import MessageActions from './MessageActions'
import MessageTimestamp from './MessageTimestamp'
import InlineChart from './InlineChart'
import MarkdownRenderer from './MarkdownRenderer'

export default function MessageBubble({ message, onOpenFile, onRetry, onDelete, onCopy, onEdit }) {
  const { role, content, tool_calls: toolCalls, timestamp } = message
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
      <div className={`message ${role} message-editing`}>
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
    <div className={`message ${role}`}>
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
