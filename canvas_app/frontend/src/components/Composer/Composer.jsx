import { useState, useRef, useEffect, useCallback } from 'react'

export default function Composer({ streaming, onSend, onStop, onInsertTemplate, templatePicker }) {
  const [value, setValue] = useState('')
  const [images, setImages] = useState([])
  const [dragging, setDragging] = useState(false)
  const textareaRef = useRef(null)
  const fileInputRef = useRef(null)

  useEffect(() => {
    if (!streaming && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [streaming])

  const handleSend = () => {
    const trimmed = value.trim()
    if ((!trimmed && images.length === 0) || streaming) return
    onSend(trimmed, images)
    setValue('')
    setImages([])
  }

  const handleInsert = (template) => {
    setValue(prev => {
      const newVal = prev ? prev + '\n' + template.prompt : template.prompt
      return newVal
    })
    if (onInsertTemplate) {
      onInsertTemplate(template)
    }
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus()
        textareaRef.current.style.height = 'auto'
        textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
      }
    }, 0)
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

  const addImage = useCallback((file) => {
    if (!file || !file.type.startsWith('image/')) return
    const reader = new FileReader()
    reader.onload = (e) => {
      setImages(prev => [...prev, {
        id: `img-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        name: file.name,
        dataUrl: e.target.result,
        file,
      }])
    }
    reader.readAsDataURL(file)
  }, [])

  const removeImage = useCallback((id) => {
    setImages(prev => prev.filter(img => img.id !== id))
  }, [])

  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) addImage(file)
      }
    }
  }, [addImage])

  const handleFileChange = useCallback((e) => {
    const files = e.target.files
    if (!files) return
    for (const file of files) addImage(file)
    e.target.value = ''
  }, [addImage])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragging(false)
    const files = e.dataTransfer?.files
    if (!files) return
    for (const file of files) addImage(file)
  }, [addImage])

  const hasContent = value.trim() || images.length > 0

  return (
    <div
      className={`composer ${dragging ? 'composer-dragging' : ''}`}
      role="form"
      aria-label="Message composer"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {dragging && <div className="composer-drop-overlay">Drop images here</div>}

      {images.length > 0 && (
        <div className="composer-images">
          {images.map(img => (
            <div key={img.id} className="composer-image-preview">
              <img src={img.dataUrl} alt={img.name} />
              <button className="composer-image-remove" onClick={() => removeImage(img.id)} aria-label={`Remove ${img.name}`}>✕</button>
            </div>
          ))}
        </div>
      )}

      <div className="composer-tools">
        <button className="toolbar-btn" onClick={() => fileInputRef.current?.click()} aria-label="Attach image">
          🖼
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        {templatePicker && onInsertTemplate && (
          <templatePicker.type {...templatePicker.props} onInsert={handleInsert} />
        )}
      </div>
      <textarea
        ref={textareaRef}
        className="composer-textarea"
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        onPaste={handlePaste}
        placeholder={streaming ? 'Generating...' : 'Ask anything... (Shift+Enter for new line, paste images)'}
        aria-label="Message input"
        rows={1}
        disabled={streaming}
      />
      {streaming ? (
        <button
          className="composer-send"
          onClick={onStop}
          aria-label="Stop generating"
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
          disabled={!hasContent}
          aria-label="Send message"
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
