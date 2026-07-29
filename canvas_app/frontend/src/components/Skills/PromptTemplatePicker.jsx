import { useState, useRef, useEffect } from 'react'

export default function PromptTemplatePicker({ skill, onInsert }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!skill || !skill.promptTemplates || skill.promptTemplates.length === 0) return null

  return (
    <div className="template-picker" ref={ref}>
      <button
        className="toolbar-btn template-picker-trigger"
        onClick={() => setOpen(!open)}
        title="Insert prompt template"
      >
        📋 Templates
      </button>
      {open && (
        <div className="template-picker-dropdown">
          <div className="template-picker-header">
            {skill.name} Prompts
          </div>
          {skill.promptTemplates.map((t, i) => (
            <div
              key={t.id}
              className="template-picker-item"
              onClick={() => { onInsert(t); setOpen(false) }}
            >
              <span className="template-picker-num">{i + 1}</span>
              <div className="template-picker-item-body">
                <div className="template-picker-item-label">{t.label}</div>
                <div className="template-picker-item-preview">{t.prompt.slice(0, 60)}…</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
