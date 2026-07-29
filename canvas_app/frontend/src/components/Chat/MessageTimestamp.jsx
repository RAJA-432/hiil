export default function MessageTimestamp({ timestamp }) {
  if (!timestamp) return null

  const d = new Date(timestamp)
  const now = new Date()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  let label
  if (mins < 1) label = 'Just now'
  else if (mins < 60) label = `${mins}m ago`
  else if (hours < 24) label = `${hours}h ago`
  else if (days < 7) label = `${days}d ago`
  else label = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })

  return (
    <span className="message-timestamp" title={d.toLocaleString()}>
      {label}
    </span>
  )
}
