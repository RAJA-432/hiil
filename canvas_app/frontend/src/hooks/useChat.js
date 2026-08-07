import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage, loadConversationMessages } from '../api/chat'

export function useChat(conversationId, onUndoPush) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [ragChunks, setRagChunks] = useState([])
  const [activityLogs, setActivityLogs] = useState([])
  const [phases, setPhases] = useState([])
  const [error, setError] = useState(null)
  const cancelRef = useRef(null)
  const mountedRef = useRef(false)
  const streamRef = useRef(null)
  const messagesRef = useRef(messages)
  const tokenBufferRef = useRef('')
  const tokenFlushScheduledRef = useRef(false)
  const tokenFlushRafRef = useRef(0)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  useEffect(() => {
    setRagChunks([])
    setActivityLogs([])
    setPhases([])
    setError(null)
  }, [conversationId])

  const loadMessages = useCallback(async (overrideConvId) => {
    const cid = overrideConvId || conversationId
    if (!cid) { setMessages([]); return }
    const msgs = await loadConversationMessages(cid)
    if (mountedRef.current) setMessages(msgs)
  }, [conversationId])

  const flushPendingTokens = useCallback(() => {
    tokenFlushScheduledRef.current = false
    tokenFlushRafRef.current = 0
    const chunk = tokenBufferRef.current
    tokenBufferRef.current = ''
    if (chunk) setStreamingText(prev => prev + chunk)
  }, [])

  const scheduleTokenFlush = useCallback(() => {
    if (tokenFlushScheduledRef.current) return
    tokenFlushScheduledRef.current = true
    tokenFlushRafRef.current = requestAnimationFrame(flushPendingTokens)
  }, [flushPendingTokens])

  const discardPendingTokens = useCallback(() => {
    tokenBufferRef.current = ''
    if (tokenFlushScheduledRef.current) {
      cancelAnimationFrame(tokenFlushRafRef.current)
      tokenFlushScheduledRef.current = false
      tokenFlushRafRef.current = 0
    }
  }, [])

  const runStream = useCallback((text, images, msgId, overrideConvId) => {
    const cid = overrideConvId || conversationId
    const toolCalls = []
    const chunks = []
    const logs = []
    const phases = []
    const abortController = new AbortController()

    discardPendingTokens()
    setPhases([])
    setStreaming(true)
    setStreamingText('')
    setError(null)
    setMessages(prev => [...prev, { id: msgId, role: 'user', content: text, images, timestamp: new Date().toISOString(), tool_calls: [], artifacts: [] }])

    const stream = sendMessage(cid, text, images,
      (event) => {
        if (!mountedRef.current) return
        if (event.type === 'tokens') {
          tokenBufferRef.current += event.text
          scheduleTokenFlush()
        } else if (event.type === 'tool_event') {
          const existing = toolCalls.find(t => t.tool === event.tool && t.status === 'running')
          if (existing) {
            existing.status = event.status
            existing.result = event.result
          } else {
            toolCalls.push({ tool: event.tool, args: event.args, status: event.status, result: event.result })
          }
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = { ...last, tool_calls: [...toolCalls] }
            }
            return copy
          })
        } else if (event.type === 'rag_context') {
          for (const chunk of (event.chunks || [])) {
            chunks.push(chunk)
          }
          setRagChunks([...chunks])
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = { ...last, rag_chunks: [...chunks] }
            }
            return copy
          })
        } else if (event.type === 'log') {
          logs.push({ ...event, timestamp: Date.now() })
          setActivityLogs([...logs])
        } else if (event.type === 'state') {
          phases.push({ agent_id: event.agent_id, phase: event.phase, timestamp: event.timestamp, iteration: event.iteration })
          setPhases([...phases])
        }
      },
      (err) => {
        if (mountedRef.current) {
          console.error('Stream error:', err)
          setError(err.message || 'Stream failed')
        }
      },
      abortController.signal,
    )

    cancelRef.current = stream
    streamRef.current = stream
    return stream
  }, [conversationId, scheduleTokenFlush, discardPendingTokens])

  const send = useCallback(async (text, images, overrideConvId) => {
    const cid = overrideConvId || conversationId
    if (!cid || !text.trim() || !mountedRef.current) return
    const msgId = `temp-${Date.now()}`
    const stream = runStream(text, images, msgId, overrideConvId)
    await stream.done.catch(() => {})
    if (mountedRef.current) {
      flushPendingTokens()
      setStreaming(false)
      setStreamingText('')
      await loadMessages(cid).catch(() => {})
    }
  }, [conversationId, loadMessages, runStream, flushPendingTokens])

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.cancel()
      streamRef.current = null
    }
    cancelRef.current = null
    discardPendingTokens()
    setStreaming(false)
    setStreamingText('')
  }, [discardPendingTokens])

  const editMessage = useCallback(async (msg, newText) => {
    if (!mountedRef.current || !conversationId) return
    const current = messagesRef.current
    const msgIndex = current.findIndex(m => m.id === msg.id)
    if (msgIndex === -1) return
    const snapshot = [...current]
    const msgsToKeep = current.slice(0, msgIndex)
    setMessages(msgsToKeep)
    setRagChunks([])
    setActivityLogs([])
    setPhases([])
    if (onUndoPush) {
      onUndoPush({
        type: 'edit-message',
        message: 'Message edited',
        data: { messages: snapshot },
        undo: (data) => { setMessages(data.messages) },
      })
    }
    const msgId = `temp-${Date.now()}`
    const stream = runStream(newText, null, msgId)
    await stream.done.catch(() => {})
    if (mountedRef.current) {
      flushPendingTokens()
      setStreaming(false)
      setStreamingText('')
      await loadMessages().catch(() => {})
    }
  }, [conversationId, loadMessages, runStream, onUndoPush, flushPendingTokens])

  const deleteMessage = useCallback((id) => {
    setMessages(prev => {
      const msg = prev.find(m => m.id === id)
      if (onUndoPush && msg) {
        onUndoPush({
          type: 'delete-message',
          message: 'Message deleted',
          data: { id, message: msg, messages: [...prev] },
          undo: (data) => { setMessages(data.messages) },
        })
      }
      return prev.filter(m => m.id !== id)
    })
  }, [onUndoPush])

  return { messages, streaming, streamingText, ragChunks, activityLogs, phases, error, send, stop, loadMessages, setMessages, editMessage, deleteMessage }
}
