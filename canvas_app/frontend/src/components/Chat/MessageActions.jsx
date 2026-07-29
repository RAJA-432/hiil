import { useState, useCallback } from 'react'

export default function MessageActions({ message, onRetry, onDelete, onCopy, onEdit }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    const text = typeof message?.content === 'string' ? message.content : ''
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {})
    onCopy?.(message)
  }, [message, onCopy])

  if (message.role === 'system') return null

  return (
    <div className="message-actions">
      {onEdit && (
        <button className="message-action-btn" onClick={onEdit} aria-label="Edit message">Edit</button>
      )}
      <button className="message-action-btn" onClick={handleCopy} aria-label={copied ? 'Copied' : 'Copy message'}>
        {copied ? '✓' : 'Copy'}
      </button>
      {message.role === 'user' && onRetry && (
        <button className="message-action-btn" onClick={() => onRetry(message)} aria-label="Retry message">Retry</button>
      )}
      {onDelete && (
        <button className="message-action-btn" onClick={() => onDelete(message.id)} aria-label="Delete message">Delete</button>
      )}
    </div>
  )
}
