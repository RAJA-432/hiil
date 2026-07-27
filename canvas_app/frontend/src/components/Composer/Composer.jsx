import { useState, useRef, useEffect } from 'react'

export default function Composer({ streaming, onSend, onStop }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)

  useEffect(() => {
    if (!streaming && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [streaming])

  const handleSend = () => {
    const trimmed = value.trim()
    if (!trimmed || streaming) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
    if (e.key === 'Escape' && streaming) {
      onStop()
    }
  }

  const handleInput = (e) => {
    setValue(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px'
  }

  return (
    <div className="composer">
      <textarea
        ref={textareaRef}
        className="composer-textarea"
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={streaming ? 'Generating...' : 'Ask anything... (Shift+Enter for new line)'}
        rows={1}
        disabled={streaming}
      />
      {streaming ? (
        <button
          className="composer-send"
          onClick={onStop}
          title="Stop generating"
          style={{ background: 'var(--error)' }}
        >
          <svg viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="2" />
          </svg>
        </button>
      ) : (
        <button
          className="composer-send"
          onClick={handleSend}
          disabled={!value.trim()}
          title="Send"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      )}
    </div>
  )
}
