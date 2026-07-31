import { useUIContext } from '../../context/UIContext'

export default function ToastContainer() {
  const { toasts, removeToast } = useUIContext()
  if (!toasts || toasts.length === 0) return null

  const latestMessage = toasts[toasts.length - 1]

  return (
    <div className="toast-container" aria-live="assertive" aria-relevant="additions removals">
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {latestMessage && `${latestMessage.type}: ${latestMessage.message}`}
      </div>
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
