import formatDate from '../../utils/formatDate'

export default function MessageTimestamp({ timestamp }) {
  if (!timestamp) return null

  const label = formatDate(timestamp)
  if (!label) return null

  return (
    <span className="message-timestamp" title={new Date(timestamp).toLocaleString()}>
      {label}
    </span>
  )
}
