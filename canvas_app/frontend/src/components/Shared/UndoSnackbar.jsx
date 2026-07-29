export default function UndoSnackbar({ items, onUndo, onDismiss }) {
  if (!items || items.length === 0) return null

  return (
    <div className="undo-snackbar-container">
      {items.map(item => (
        <div key={item.id} className="undo-snackbar">
          <span className="undo-snackbar-message">{item.message}</span>
          <button className="undo-snackbar-btn" onClick={() => { onUndo(item); onDismiss(item.id) }}>
            Undo
          </button>
          <button className="undo-snackbar-close" onClick={() => onDismiss(item.id)}>✕</button>
        </div>
      ))}
    </div>
  )
}
