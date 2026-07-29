import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage, loadConversationMessages } from '../api/chat'

export function useChat(conversationId, onUndoPush) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [ragChunks, setRagChunks] = useState([])
  const [activityLogs, setActivityLogs] = useState([])
  const [error, setError] = useState(null)
  const cancelRef = useRef(null)
  const mountedRef = useRef(false)
  const streamRef = useRef(null)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    setRagChunks([])
    setActivityLogs([])
    setError(null)
  }, [conversationId])

  const loadMessages = useCallback(async () => {
    if (!conversationId) { setMessages([]); return }
    const msgs = await loadConversationMessages(conversationId)
    if (mountedRef.current) setMessages(msgs)
  }, [conversationId])

  const runStream = useCallback((text, images, msgId) => {
    const toolCalls = []
    const chunks = []
    const logs = []
    const abortController = new AbortController()
    const body = images?.length > 0
      ? JSON.stringify({ text, images: images.map(i => i.dataUrl) })
      : text

    setStreaming(true)
    setStreamingText('')
    setError(null)
    setMessages(prev => [...prev, { id: msgId, role: 'user', content: text, images, timestamp: new Date().toISOString(), tool_calls: [], artifacts: [] }])

    const stream = sendMessage(conversationId, body,
      (event) => {
        if (!mountedRef.current) return
        if (event.type === 'tokens') {
          setStreamingText(event.text)
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
              last.tool_calls = [...toolCalls]
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
              last.rag_chunks = [...chunks]
            }
            return copy
          })
        } else if (event.type === 'log') {
          logs.push({ ...event, timestamp: Date.now() })
          setActivityLogs([...logs])
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
  }, [conversationId])

  const send = useCallback(async (text, images) => {
    if (!conversationId || !text.trim() || !mountedRef.current) return
    const msgId = `temp-${Date.now()}`
    const stream = runStream(text, images, msgId)
    try { await stream.done } catch {}
    if (mountedRef.current) {
      setStreaming(false)
      setStreamingText('')
      try { await loadMessages() } catch {}
    }
  }, [conversationId, loadMessages, runStream])

  const stop = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.cancel()
      streamRef.current = null
    }
    cancelRef.current = null
    setStreaming(false)
    setStreamingText('')
  }, [])

  const editMessage = useCallback(async (msg, newText) => {
    if (!mountedRef.current || !conversationId) return
    const msgIndex = messages.findIndex(m => m.id === msg.id)
    if (msgIndex === -1) return
    const msgsToKeep = messages.slice(0, msgIndex)
    setMessages(msgsToKeep)
    setRagChunks([])
    setActivityLogs([])
    const msgId = `temp-${Date.now()}`
    const stream = runStream(newText, null, msgId)
    try { await stream.done } catch {}
    if (mountedRef.current) {
      setStreaming(false)
      setStreamingText('')
      try { await loadMessages() } catch {}
    }
  }, [conversationId, messages, loadMessages, runStream])

  const deleteMessage = useCallback((id) => {
    const msg = messages.find(m => m.id === id)
    setMessages(prev => prev.filter(m => m.id !== id))
    if (onUndoPush && msg) {
      onUndoPush({
        type: 'delete-message',
        message: 'Message deleted',
        data: { id, message: msg, messages: [...messages] },
        undo: (data) => { setMessages(data.messages) },
      })
    }
  }, [messages, onUndoPush])

  return { messages, streaming, streamingText, ragChunks, activityLogs, error, send, stop, loadMessages, setMessages, editMessage, deleteMessage }
}
