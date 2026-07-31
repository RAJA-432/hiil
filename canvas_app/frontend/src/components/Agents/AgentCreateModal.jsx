import { useState } from 'react'
import Modal from '../Shared/Modal'

export default function AgentCreateModal({ open, onClose, onCreate }) {
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [capsInput, setCapsInput] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [creating, setCreating] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim() || !role.trim()) return
    setCreating(true)
    try {
      const capabilities = capsInput.split(',').map(c => c.trim()).filter(Boolean)
      await onCreate({ name: name.trim(), role: role.trim(), capabilities, system_prompt: systemPrompt.trim() })
      setName('')
      setRole('')
      setCapsInput('')
      setSystemPrompt('')
      onClose()
    } catch { } finally {
      setCreating(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Create Agent">
      <form className="agent-create-form" onSubmit={handleSubmit}>
        <label className="agent-form-field">
          <span>Name *</span>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Data Analyst"
            required
            autoFocus
          />
        </label>
        <label className="agent-form-field">
          <span>Role *</span>
          <input
            type="text"
            value={role}
            onChange={e => setRole(e.target.value)}
            placeholder="e.g. Analyze data and create visualizations"
            required
          />
        </label>
        <label className="agent-form-field">
          <span>Capabilities (comma-separated)</span>
          <input
            type="text"
            value={capsInput}
            onChange={e => setCapsInput(e.target.value)}
            placeholder="e.g. python, sql, charting"
          />
        </label>
        <label className="agent-form-field">
          <span>System Prompt</span>
          <textarea
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            placeholder="Optional system prompt for the agent..."
            rows={4}
          />
        </label>
        <div className="agent-form-actions">
          <button type="button" className="agent-btn" onClick={onClose}>Cancel</button>
          <button type="submit" className="agent-btn agent-btn-primary" disabled={creating || !name.trim() || !role.trim()}>
            {creating ? 'Creating...' : 'Create Agent'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
