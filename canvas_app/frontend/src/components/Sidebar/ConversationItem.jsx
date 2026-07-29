import { useState, useRef, useEffect, useCallback } from 'react'
import TagManager from './TagManager'
import ConfirmDialog from '../Shared/ConfirmDialog'

export default function ConversationItem({ conversation, active, onSelect, onDelete, onRename, tags, onAddTag, onRemoveTag, pinned, onTogglePin }) {
  const [editing, setEditing] = useState(false)
  const [editTitle, setEditTitle] = useState(conversation.title || '')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [editing])

  const handleDoubleClick = useCallback((e) => {
    e.stopPropagation()
    setEditTitle(conversation.title || '')
    setEditing(true)
  }, [conversation.title])

  const handleSave = useCallback(() => {
    const title = editTitle.trim() || conversation.title || 'Untitled'
    setEditing(false)
    if (title !== (conversation.title || '')) {
      onRename?.(conversation.id, title)
    }
  }, [editTitle, conversation, onRename])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') handleSave()
    if (e.key === 'Escape') setEditing(false)
  }, [handleSave])

  const handleDelete = useCallback((e) => {
    e.stopPropagation()
    setConfirmOpen(true)
  }, [])

  const handleConfirmDelete = useCallback(() => {
    setConfirmOpen(false)
    onDelete?.(conversation.id)
  }, [conversation.id, onDelete])

  const handleCancelDelete = useCallback(() => {
    setConfirmOpen(false)
  }, [])

  const handlePin = useCallback((e) => {
    e.stopPropagation()
    onTogglePin?.(conversation.id)
  }, [conversation.id, onTogglePin])

  if (editing) {
    return (
      <div className="conversation-item editing" onClick={e => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="conversation-rename-input"
          value={editTitle}
          onChange={e => setEditTitle(e.target.value)}
          onBlur={handleSave}
          onKeyDown={handleKeyDown}
        />
      </div>
    )
  }

  return (
    <div
      className={`conversation-item ${active ? 'active' : ''} ${pinned ? 'pinned' : ''}`}
      onClick={() => onSelect(conversation)}
      onDoubleClick={handleDoubleClick}
      role="button"
      tabIndex={0}
      aria-selected={active}
      aria-label={conversation.title || 'Untitled'}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(conversation) } }}
    >
      <button className="conversation-pin" onClick={handlePin} aria-label={pinned ? 'Unpin conversation' : 'Pin conversation'}>
        {pinned ? '📌' : '📍'}
      </button>
      <div className="conversation-item-body">
        <span className="conversation-item-title">{conversation.title || 'Untitled'}</span>
        <TagManager
          conversationId={conversation.id}
          tags={tags}
          onAddTag={onAddTag}
          onRemoveTag={onRemoveTag}
        />
      </div>
      <button className="conversation-item-delete" onClick={handleDelete} aria-label="Delete conversation">✕</button>
      <ConfirmDialog
        isOpen={confirmOpen}
        title="Delete conversation?"
        message="This will permanently delete this conversation and all its messages."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
      />
    </div>
  )
}
