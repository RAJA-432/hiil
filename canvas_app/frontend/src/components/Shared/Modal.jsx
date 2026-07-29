import { useEffect, useRef, useCallback } from 'react'

export default function Modal({ open, onClose, title, children, width = 520 }) {
  const overlayRef = useRef(null)
  const panelRef = useRef(null)
  const previousActiveElement = useRef(null)

  useEffect(() => {
    if (!open) return
    previousActiveElement.current = document.activeElement
    const handler = (e) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusable.length === 0) return
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handler)
    return () => {
      document.removeEventListener('keydown', handler)
      previousActiveElement.current?.focus()
    }
  }, [open, onClose])

  if (!open) return null

  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose()
  }

  return (
    <div className="modal-overlay" ref={overlayRef} onClick={handleOverlayClick} role="presentation">
      <div className="modal-panel" ref={panelRef} style={{ maxWidth: width }} role="dialog" aria-modal="true" aria-label={title || 'Dialog'}>
        <div className="modal-header">
          <h3 className="modal-title">{title}</h3>
          <button className="modal-close" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">
          {children}
        </div>
      </div>
    </div>
  )
}
