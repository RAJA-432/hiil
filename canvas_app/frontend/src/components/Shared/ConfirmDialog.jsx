import { useEffect, useRef } from 'react'
import Modal from './Modal'

export default function ConfirmDialog({ isOpen, title, message, confirmLabel = 'Delete', cancelLabel = 'Cancel', onConfirm, onCancel, variant = 'danger' }) {
  const confirmRef = useRef(null)

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => confirmRef.current?.focus(), 0)
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e) => {
      if (e.key === 'Enter' && document.activeElement?.closest('.modal-panel')) {
        e.preventDefault()
        onConfirm?.()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [isOpen, onConfirm])

  return (
    <Modal open={isOpen} onClose={onCancel} title={title} width={420}>
      <p style={{ margin: '0 0 20px', color: 'var(--text-secondary)', lineHeight: 1.5, fontSize: 14 }}>{message}</p>
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button className="toolbar-btn" onClick={onCancel}>{cancelLabel}</button>
        <button
          ref={confirmRef}
          style={{
            padding: '8px 20px',
            background: variant === 'danger' ? 'var(--error)' : 'var(--primary)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500,
          }}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}
