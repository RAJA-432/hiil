import { useEffect, useRef, useState } from 'react'
import { fetchUsage } from '../../api/chat'

const FETCH_DEBOUNCE_MS = 1500

export default function TokenBar({ messages, maxTokens = 128000, sessionId }) {
  const [usage, setUsage] = useState(null)
  const mountedRef = useRef(true)
  const timerRef = useRef(null)
  const activeSessionRef = useRef(null)
  const skipDebounceRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setUsage(null)
    if (!sessionId) return
    skipDebounceRef.current = true
    activeSessionRef.current = sessionId
    fetchUsage(sessionId).then(u => {
      if (mountedRef.current && activeSessionRef.current === sessionId) setUsage(u)
    }).catch(() => {})
  }, [sessionId])

  useEffect(() => {
    if (!sessionId || !messages || messages.length === 0) return
    if (skipDebounceRef.current) {
      skipDebounceRef.current = false
      return
    }
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      if (!mountedRef.current || activeSessionRef.current !== sessionId) return
      fetchUsage(sessionId).then(u => {
        if (mountedRef.current && activeSessionRef.current === sessionId) setUsage(u)
      }).catch(() => {})
    }, FETCH_DEBOUNCE_MS)
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
