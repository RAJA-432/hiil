import { useCallback, useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble'
import MarkdownRenderer from './MarkdownRenderer'
import { MessageSkeleton } from '../Shared/LoadingSkeleton'
import ArchitectureCard from '../Shared/ArchitectureCard'

const WINDOW_SIZE = 100
const OLDER_CHUNK_SIZE = 50
const NEAR_BOTTOM_THRESHOLD = 150
const LOAD_OLDER_THRESHOLD = 80

export default function WindowedMessageList({
  messages, streamingText, showStreaming, error, loading, activeConversation, scrollToMessageId,
  containerRef, bottomRef, onOpenFile, onRetry, onDelete, onCopy, onEdit,
}) {
  const [startIndex, setStartIndex] = useState(() => Math.max(0, messages.length - WINDOW_SIZE))
  const isNearBottomRef = useRef(true)
  const pendingScrollRestoreRef = useRef(null)
  const restoreScrollRafRef = useRef(null)
  const loadingOlderRef = useRef(false)
  const conversationId = activeConversation?.id
  const messagesLengthRef = useRef(messages.length)

  useEffect(() => {
    messagesLengthRef.current = messages.length
  }, [messages.length])

  useEffect(() => {
    if (isNearBottomRef.current) {
      setStartIndex(Math.max(0, messagesLengthRef.current - WINDOW_SIZE))
    }
  }, [messagesLengthRef, messages.length])

  useEffect(() => {
    isNearBottomRef.current = true
    setStartIndex(Math.max(0, messagesLengthRef.current - WINDOW_SIZE))
  }, [conversationId, messagesLengthRef])

  useEffect(() => {
    const container = containerRef.current
    if (container && isNearBottomRef.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingText, containerRef, bottomRef])

  const loadOlder = useCallback(() => {
    if (loadingOlderRef.current || startIndex <= 0) return
    loadingOlderRef.current = true
    const container = containerRef.current
    const prevScrollHeight = container ? container.scrollHeight : 0
    const prevScrollTop = container ? container.scrollTop : 0
    pendingScrollRestoreRef.current = { prevScrollHeight, prevScrollTop }
    setStartIndex(Math.max(0, startIndex - OLDER_CHUNK_SIZE))
  }, [startIndex, containerRef])

  useEffect(() => {
    const pending = pendingScrollRestoreRef.current
    if (!pending) return
    pendingScrollRestoreRef.current = null
    if (restoreScrollRafRef.current) {
      cancelAnimationFrame(restoreScrollRafRef.current)
    }
    restoreScrollRafRef.current = requestAnimationFrame(() => {
      restoreScrollRafRef.current = null
      const container = containerRef.current
      if (container) {
        container.scrollTop = pending.prevScrollTop + (container.scrollHeight - pending.prevScrollHeight)
      }
      loadingOlderRef.current = false
    })
  }, [startIndex, containerRef])

  useEffect(() => {
    return () => {
      if (restoreScrollRafRef.current) {
        cancelAnimationFrame(restoreScrollRafRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const handleScroll = () => {
      isNearBottomRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < NEAR_BOTTOM_THRESHOLD
      if (container.scrollTop < LOAD_OLDER_THRESHOLD && startIndex > 0) {
        loadOlder()
      }
    }
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [containerRef, startIndex, loadOlder])

  useEffect(() => {
    if (!scrollToMessageId || messages.length === 0) return
    const index = messages.findIndex(m => String(m.id) === String(scrollToMessageId))
    if (index === -1) return
    setStartIndex(Math.max(0, index - 4))
  }, [scrollToMessageId, messages])

  const visibleMessages = startIndex > 0 ? messages.slice(startIndex) : messages

  return (
    <div className="chat-messages" ref={containerRef} role="log" aria-label="Chat messages" aria-live="polite">
      {!activeConversation ? (
        <div className="chat-empty">
          <ArchitectureCard />
        </div>
      ) : loading ? (
        <MessageSkeleton count={4} />
      ) : messages.length === 0 && !showStreaming ? (
        <div className="chat-empty">
          <h2>{activeConversation.title}</h2>
          <p>Ask a question or describe what you&apos;d like to build.</p>
        </div>
      ) : (
        <>
          {visibleMessages.map((msg, i) => (
            <MessageBubble
              key={msg.id || i}
              message={msg}
              onOpenFile={onOpenFile}
              onRetry={onRetry}
              onDelete={onDelete}
              onCopy={onCopy}
              onEdit={onEdit}
            />
          ))}
          {error && (
            <div className="message assistant">
              <div className="message-content" style={{ color: 'var(--error)', border: '1px solid var(--error)', borderRadius: 'var(--radius-md)', padding: '10px 16px', background: 'rgba(248,113,113,0.06)' }}>
                {error}
              </div>
            </div>
          )}
          {showStreaming && (
            <div className="message assistant">
              <div className="message-content">
                <MarkdownRenderer content={streamingText} />
                <span className="streaming-cursor" />
              </div>
            </div>
          )}
        </>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
