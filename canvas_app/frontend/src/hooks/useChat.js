import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage, loadConversationMessages } from '../api/chat'

export function useChat(conversationId) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const cancelRef = useRef(null)
  const mountedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const loadMessages = useCallback(async () => {
    if (!conversationId) { setMessages([]); return }
    const msgs = await loadConversationMessages(conversationId)
    if (mountedRef.current) setMessages(msgs)
  }, [conversationId])

  const send = useCallback(async (text) => {
    if (!conversationId || !text.trim()) return

    if (mountedRef.current) {
      setStreaming(true)
    }
    if (mountedRef.current) {
      setStreamingText('')
    }

    const toolCalls = []
    const abortController = new AbortController()

    cancelRef.current = sendMessage(conversationId, text,
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
        }
      },
      () => {},
      abortController.signal,
    )

    if (mountedRef.current) {
      setMessages(prev => [...prev, { id: `temp-${Date.now()}`, role: 'user', content: text, timestamp: new Date().toISOString(), tool_calls: [], artifacts: [] }])
    }

    try {
      await loadMessages()
    } finally {
      if (mountedRef.current) {
        setStreaming(false)
        setStreamingText('')
      }
    }
  }, [conversationId, loadMessages])

  const stop = useCallback(() => {
    if (cancelRef.current) {
      cancelRef.current()
      cancelRef.current = null
    }
    setStreaming(false)
    setStreamingText('')
  }, [])

  return { messages, streaming, streamingText, send, stop, loadMessages, setMessages }
}