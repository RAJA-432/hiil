import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage, loadConversationMessages } from '../api/chat'

export function useChat(conversationId) {
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const cancelRef = useRef(null)
  const mountedRef = useRef(false)
  const streamPromiseRef = useRef(null)

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

    if (!mountedRef.current) return
    setStreaming(true)
    setStreamingText('')

    const toolCalls = []
    const abortController = new AbortController()

    if (mountedRef.current) {
      setMessages(prev => [...prev, { id: `temp-${Date.now()}`, role: 'user', content: text, timestamp: new Date().toISOString(), tool_calls: [], artifacts: [] }])
    }

    const cancel = sendMessage(conversationId, text,
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
      (err) => {
        if (mountedRef.current) console.error('Stream error:', err)
      },
      abortController.signal,
    )

    cancelRef.current = cancel
    streamPromiseRef.current = { cancel }

    await new Promise((resolve) => {
      const check = () => {
        if (!mountedRef.current) return resolve()
        setTimeout(() => {
          loadMessages().then(() => {
            if (mountedRef.current) {
              setStreaming(false)
              setStreamingText('')
            }
            resolve()
          }).catch(() => resolve())
        }, 100)
      }
      check()
    })
  }, [conversationId, loadMessages])

  const stop = useCallback(() => {
    if (streamPromiseRef.current) {
      streamPromiseRef.current.cancel()
      streamPromiseRef.current = null
    }
    cancelRef.current = null
    setStreaming(false)
    setStreamingText('')
  }, [])

  return { messages, streaming, streamingText, send, stop, loadMessages, setMessages }
}