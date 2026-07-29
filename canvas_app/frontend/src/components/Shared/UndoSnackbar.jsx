import { useChatContext } from '../../context/ChatContext'

export default function UndoSnackbar() {
  const { undoItems, handleUndo, dismissUndo } = useChatContext()
  if (!undoItems || undoItems.length === 0) return null

  return (
    <div className="undo-snackbar-container">
      {undoItems.map(item => (
        <div key={item.id} className="undo-snackbar">
          <span className="undo-snackbar-message">{item.message}</span>
          <button className="undo-snackbar-btn" onClick={() => { handleUndo(item); dismissUndo(item.id) }}>
            Undo
          </button>
          <button className="undo-snackbar-close" onClick={() => dismissUndo(item.id)}>✕</button>
        </div>
      ))}
    </div>
  )
}
