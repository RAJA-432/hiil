import { useEffect, useState } from 'react'
import { fetchUsage } from '../../api/chat'

export default function TokenBar({ messages, maxTokens = 128000, sessionId }) {
  const [usage, setUsage] = useState(null)

  useEffect(() => {
    let mounted = true
    setUsage(null)
    fetchUsage(sessionId).then(u => { if (mounted) setUsage(u) }).catch(() => {})
    return () => { mounted = false }
  }, [sessionId, messages])

  const estimateTokens = (text) => Math.ceil((text || '').length / 4)
  const estimatedTotal = messages ? messages.reduce((sum, m) => sum + estimateTokens(m.content), 0) : 0

  const sessionUsage = usage?.session
  const hasRealUsage = sessionUsage && sessionUsage.total_tokens > 0
  const total = hasRealUsage ? sessionUsage.total_tokens : estimatedTotal
  const pct = Math.min(100, (total / maxTokens) * 100)

  let barClass = 'token-bar-fill'
  if (pct > 90) barClass += ' token-bar-critical'
  else if (pct > 70) barClass += ' token-bar-warn'

  const breakdown = hasRealUsage
    ? `in:${sessionUsage.input_tokens} out:${sessionUsage.output_tokens}`
    : null

  const cost = hasRealUsage && sessionUsage.cost
    ? `$${sessionUsage.cost.toFixed(4)}`
    : null

  if (!messages || messages.length === 0) return null

  return (
    <div className="token-bar" title={`~${total.toLocaleString()} / ${maxTokens.toLocaleString()} tokens`} role="status" aria-label={`Token usage: ${Math.round(pct)} percent`}>
      <div className="token-bar-track">
        <div className={barClass} style={{ width: `${pct}%` }} />
      </div>
      <span className="token-bar-label">{Math.round(pct)}%</span>
      {breakdown && <span className="token-bar-breakdown">{breakdown}</span>}
      {cost && <span className="token-bar-cost">{cost}</span>}
    </div>
  )
}
