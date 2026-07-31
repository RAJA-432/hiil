import { useState, useEffect, useRef } from 'react'
import Modal from '../Shared/Modal'

function InterruptDialog({ event, onDecision }) {
  const [decisionType, setDecisionType] = useState('approve')
  const [message, setMessage] = useState('')
  const action = event?.action_requests?.[0]

  if (!action) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    onDecision({
      type: decisionType,
      edited_action: decisionType === 'edit' ? { name: action.name, args: action.args } : null,
      message: decisionType === 'reject' || decisionType === 'respond' ? message : null,
    })
  }

  return (
    <div className="agent-interrupt">
      <div className="agent-interrupt-header">
        <span className="agent-interrupt-icon">⚠</span>
        <span>Action Requires Approval</span>
      </div>
      <div className="agent-interrupt-tool">
        <strong>Tool:</strong> {action.name}
      </div>
      <div className="agent-interrupt-args">
        <strong>Arguments:</strong>
        <pre>{JSON.stringify(action.args, null, 2)}</pre>
      </div>
      <form onSubmit={handleSubmit} className="agent-interrupt-form">
        <div className="agent-interrupt-options">
          {action.allowed_decisions?.includes('approve') && (
            <label className="agent-interrupt-option">
              <input type="radio" name="decision" value="approve" checked={decisionType === 'approve'} onChange={() => setDecisionType('approve')} />
              <span>Approve</span>
            </label>
          )}
          {action.allowed_decisions?.includes('edit') && (
            <label className="agent-interrupt-option">
              <input type="radio" name="decision" value="edit" checked={decisionType === 'edit'} onChange={() => setDecisionType('edit')} />
              <span>Edit</span>
            </label>
          )}
          {action.allowed_decisions?.includes('reject') && (
            <label className="agent-interrupt-option">
              <input type="radio" name="decision" value="reject" checked={decisionType === 'reject'} onChange={() => setDecisionType('reject')} />
              <span>Reject</span>
            </label>
          )}
          <label className="agent-interrupt-option">
            <input type="radio" name="decision" value="respond" checked={decisionType === 'respond'} onChange={() => setDecisionType('respond')} />
            <span>Respond</span>
          </label>
        </div>
        {(decisionType === 'reject' || decisionType === 'respond') && (
          <label className="agent-form-field">
            <span>Message</span>
            <textarea
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Your message to the agent..."
              rows={3}
            />
          </label>
        )}
        <div className="agent-form-actions">
          <button type="submit" className="agent-btn agent-btn-primary">
            Submit Decision
          </button>
        </div>
      </form>
    </div>
  )
}

export default function AgentRunModal({ open, onClose, agent, events, running, onRun, onResume }) {
  const logEndRef = useRef(null)
  const [taskInput, setTaskInput] = useState('')
  const [showInput, setShowInput] = useState(true)
  const lastInterrupt = useRef(null)

  useEffect(() => {
    if (open && agent) {
      setShowInput(true)
      setTaskInput('')
      lastInterrupt.current = null
    }
  }, [open, agent])

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events])

  useEffect(() => {
    const interruptEvent = events.find(e => e.type === 'interrupt')
    if (interruptEvent) {
      lastInterrupt.current = interruptEvent
    }
  }, [events])

  const handleStartRun = (e) => {
    e.preventDefault()
    if (!taskInput.trim()) return
    setShowInput(false)
    lastInterrupt.current = null
    onRun(agent.agent_id, taskInput)
  }

  const handleDecision = (decision) => {
    onResume(agent.agent_id, [decision])
  }

  const lastEvent = events[events.length - 1]
  const isComplete = lastEvent?.type === 'done'
  const hasInterrupt = events.some(e => e.type === 'interrupt')

  return (
    <Modal open={open} onClose={onClose} title={`Run: ${agent?.name || ''}`} width="640px">
      <div className="agent-run-modal">
        {showInput && !hasInterrupt && !isComplete ? (
          <form onSubmit={handleStartRun} className="agent-run-input">
            <label className="agent-form-field">
              <span>Task Input</span>
              <textarea
                value={taskInput}
                onChange={e => setTaskInput(e.target.value)}
                placeholder="Describe the task for this agent..."
                rows={4}
                autoFocus
              />
            </label>
            <div className="agent-form-actions">
              <button type="submit" className="agent-btn agent-btn-primary" disabled={!taskInput.trim()}>
                Start Run
              </button>
            </div>
          </form>
        ) : null}

        {events.length > 0 && (
          <div className="agent-run-log">
            {events.map((event, i) => {
              if (event.type === 'log') {
                return <div key={i} className="agent-log-entry agent-log-info"><span className="agent-log-level">{event.level}</span> {event.text}</div>
              }
              if (event.type === 'tokens') {
                return <div key={i} className="agent-log-entry agent-log-tokens"><pre>{event.text}</pre></div>
              }
              if (event.type === 'tool_event') {
                return <div key={i} className="agent-log-entry agent-log-tool"><span className="agent-log-level">tool</span> {event.tool}: {event.status}</div>
              }
              if (event.type === 'interrupt') {
                return <div key={i} className="agent-log-entry agent-log-interrupt"><span className="agent-log-level">interrupt</span> Waiting for approval...</div>
              }
              if (event.type === 'error') {
                return <div key={i} className="agent-log-entry agent-log-error"><span className="agent-log-level">error</span> {event.message}</div>
              }
              if (event.type === 'done') {
                return <div key={i} className="agent-log-entry agent-log-done"><span className="agent-log-level">done</span> Agent completed</div>
              }
              return null
            })}
            <div ref={logEndRef} />
          </div>
        )}

        {hasInterrupt && !running && (
          <InterruptDialog
            event={lastInterrupt.current}
            onDecision={handleDecision}
          />
        )}

        {running && (
          <div className="agent-run-spinner">Running...</div>
        )}

        {isComplete && (
          <div className="agent-form-actions" style={{ marginTop: '1rem' }}>
            <button className="agent-btn" onClick={onClose}>Close</button>
          </div>
        )}
      </div>
    </Modal>
  )
}
