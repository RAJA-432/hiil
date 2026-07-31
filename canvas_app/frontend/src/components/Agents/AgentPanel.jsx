import AgentCard from './AgentCard'

export default function AgentPanel({ agents, loading, onRun, onStop, onCreate }) {
  if (loading) {
    return (
      <div className="agent-panel">
        <div className="sidebar-loading" style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading agents...</div>
      </div>
    )
  }

  return (
    <div className="agent-panel">
      <div className="agent-panel-header">
        <h3 className="agent-panel-title">Agents</h3>
        <button className="agent-btn agent-btn-primary" onClick={onCreate}>
          + New Agent
        </button>
      </div>
      {agents.length === 0 ? (
        <div className="agent-panel-empty">
          <p>No agents yet. Create one to get started.</p>
        </div>
      ) : (
        <div className="agent-list">
          {agents.map(agent => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              onRun={onRun}
              onStop={onStop}
            />
          ))}
        </div>
      )}
    </div>
  )
}
