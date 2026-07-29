import Modal from './Modal'

const SHORTCUTS = [
  { key: 'Enter', desc: 'Send message' },
  { key: 'Shift + Enter', desc: 'New line in composer' },
  { key: 'Escape', desc: 'Stop generation / close modal' },
  { key: 'Ctrl + K', desc: 'Open command palette' },
  { key: 'Ctrl + N', desc: 'New conversation' },
  { key: 'Ctrl + ,', desc: 'Open settings' },
  { key: 'Ctrl + \\', desc: 'Toggle sidebar' },
  { key: 'Ctrl + Shift + P', desc: 'Toggle preview panel' },
  { key: 'Ctrl + L', desc: 'Focus search' },
]

export default function ShortcutsModal({ open, onClose }) {
  return (
    <Modal open={open} onClose={onClose} title="Keyboard Shortcuts" width={420}>
      <div className="shortcuts-list">
        {SHORTCUTS.map((s, i) => (
          <div key={i} className="shortcut-row">
            <kbd className="shortcut-key">{s.key}</kbd>
            <span className="shortcut-desc">{s.desc}</span>
          </div>
        ))}
      </div>
    </Modal>
  )
}
