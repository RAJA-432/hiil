import { useState } from 'react'

const DEFAULT_CONNECTORS = [
  { id: 'filesystem', name: 'File System', description: 'Read, write, and manage workspace files', enabled: true, type: 'built-in' },
  { id: 'search', name: 'Web Search', description: 'Search the web for current information', enabled: true, type: 'built-in' },
  { id: 'python', name: 'Python Executor', description: 'Execute Python code in isolated environment', enabled: true, type: 'built-in' },
  { id: 'git', name: 'Git', description: 'Git operations: commit, diff, log, status', enabled: false, type: 'built-in' },
  { id: 'database', name: 'Database', description: 'Query SQL databases (configurable)', enabled: false, type: 'plugin' },
  { id: 'slack', name: 'Slack', description: 'Send and read Slack messages', enabled: false, type: 'plugin' },
  { id: 'email', name: 'Email', description: 'Send and read emails via SMTP/IMAP', enabled: false, type: 'plugin' },
  { id: 'github', name: 'GitHub', description: 'Manage issues, PRs, and repos', enabled: false, type: 'plugin' },
]

export default function ConnectorsPanel({ onClose }) {
  const [connectors, setConnectors] = useState(DEFAULT_CONNECTORS)
  const [filter, setFilter] = useState('all')

  const filtered = filter === 'all' ? connectors : filter === 'enabled' ? connectors.filter(c => c.enabled) : connectors.filter(c => c.type === filter)

  const toggleConnector = (id) => {
    setConnectors(prev => prev.map(c => c.id === id ? { ...c, enabled: !c.enabled } : c))
  }

  return (
    <div className="connectors-panel">
      <div className="connectors-header">
        <h3 className="connectors-title">Connectors</h3>
        <button className="toolbar-btn" onClick={onClose}>✕</button>
      </div>

      <div className="connectors-filters">
        {['all', 'enabled', 'built-in', 'plugin'].map(f => (
          <button
            key={f}
            className={`skills-cat-btn ${filter === f ? 'active' : ''}`}
            onClick={() => setFilter(f)}
          >
            {f === 'all' ? 'All' : f === 'enabled' ? 'Enabled' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      <div className="connectors-list">
        {filtered.map(c => (
          <div key={c.id} className={`connector-item ${c.enabled ? 'connector-enabled' : ''}`}>
            <div className="connector-info">
              <div className="connector-name">
                {c.name}
                <span className="connector-type">{c.type}</span>
              </div>
              <div className="connector-desc">{c.description}</div>
            </div>
            <label className="connector-toggle">
              <input
                type="checkbox"
                checked={c.enabled}
                onChange={() => toggleConnector(c.id)}
              />
              <span className="connector-toggle-slider" />
            </label>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <div className="connectors-empty">No connectors match this filter.</div>
      )}
    </div>
  )
}
