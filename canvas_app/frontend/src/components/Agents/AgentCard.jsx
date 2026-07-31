const STATUS_LABELS = {
  idle: 'Idle',
  running: 'Running',
  waiting: 'Waiting',
  failed: 'Failed',
}

const STATUS_COLORS = {
  idle: 'var(--text-muted)',
  running: '#34d399',
  waiting: '#fbbf24',
  failed: '#f87171',
}

export default function AgentCard({ agent, onRun, onStop }) {
  const statusColor = STATUS_COLORS[agent.status] || 'var(--text-muted)'
  const statusLabel = STATUS_LABELS[agent.status] || agent.status

  return (
    <div className="agent-card">
      <div className="agent-card-header">
        <span className="agent-card-name">{agent.name}</span>
        <span className="agent-card-status" style={{ color: statusColor }}>
          <span className="agent-status-dot" style={{ backgroundColor: statusColor }} />
          {statusLabel}
        </span>
      </div>
      <div className="agent-card-role">{agent.role}</div>
      {agent.capabilities?.length > 0 && (
        <div className="agent-card-caps">
          {agent.capabilities.map(cap => (
            <span key={cap} className="agent-cap-tag">{cap}</span>
          ))}
        </div>
      )}
      <div className="agent-card-actions">
        {agent.status === 'running' ? (
          <button className="agent-btn agent-btn-stop" onClick={() => onStop(agent.agent_id)}>
            Stop
          </button>
        ) : (
          <button className="agent-btn agent-btn-run" onClick={() => onRun(agent)}>
            Run
          </button>
        )}
      </div>
    </div>
  )
}
