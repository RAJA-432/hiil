import { useUIContext } from '../../context/UIContext'

export default function ToastContainer() {
  const { toasts, removeToast } = useUIContext()
  if (!toasts || toasts.length === 0) return null

  return (
    <div className="toast-container" aria-live="assertive" aria-relevant="additions removals">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`} onClick={() => removeToast(t.id)} role="alert">
          <span className="toast-icon" aria-hidden="true">
            {t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ'}
          </span>
          <span className="toast-message">{t.message}</span>
        </div>
      ))}
    </div>
  )
}
