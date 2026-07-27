function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function groupByDate(conversations) {
  const now = new Date()
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  const groups = { today: [], yesterday: [], thisWeek: [], earlier: [] }

  for (const c of conversations) {
    const d = new Date(c.updated || c.created)
    if (d >= today) groups.today.push(c)
    else if (d >= yesterday) groups.yesterday.push(c)
    else if (d >= lastWeek) groups.thisWeek.push(c)
    else groups.earlier.push(c)
  }

  const labels = {
    today: 'Today',
    yesterday: 'Yesterday',
    thisWeek: 'This Week',
    earlier: 'Earlier',
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([key, items]) => ({ label: labels[key], items }))
}

export default function ConversationList({ conversations, activeConversation, onSelect, onNew, onDelete }) {
  const groups = groupByDate(conversations)

  return (
    <div className="conversation-list">
      <button
        onClick={onNew}
        style={{
          width: '100%',
          padding: '8px 10px',
          marginBottom: 8,
          background: 'var(--primary-dim)',
          border: '1px solid var(--primary)',
          borderRadius: 'var(--radius-sm)',
          color: 'var(--primary)',
          cursor: 'pointer',
          fontSize: 13,
          fontWeight: 500,
        }}
      >
        + New conversation
      </button>

      {groups.map((group) => (
        <div key={group.label}>
          <div className="sidebar-section-header">{group.label}</div>
          {group.items.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${activeConversation?.id === conv.id ? 'active' : ''}`}
              onClick={() => onSelect(conv)}
            >
              <span className="truncate">{conv.title}</span>
            </div>
          ))}
        </div>
      ))}

      {conversations.length === 0 && (
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
          No conversations yet
        </div>
      )}
    </div>
  )
}
