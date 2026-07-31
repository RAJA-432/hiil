import { useEffect, useRef, useState } from 'react'
import { useChatContext } from '../../context/ChatContext'
import { useUIContext } from '../../context/UIContext'
import MessageBubble from './MessageBubble'
import MarkdownRenderer from './MarkdownRenderer'
import TokenBar from '../Shared/TokenBar'
import RetrievedChunksPanel from './RetrievedChunksPanel'
import ToolActivityPanel from './ToolActivityPanel'
import ScrollToBottom from '../Shared/ScrollToBottom'
import ConversationSearch from './ConversationSearch'
import ConversationExport from '../Shared/ConversationExport'
import SystemPromptBar from './SystemPromptBar'
import { MessageSkeleton } from '../Shared/LoadingSkeleton'

export default function ChatPanel({ onOpenFile, onCopy }) {
  const { messages, streaming, streamingText, ragChunks, activityLogs, error, activeConversation, handleRetry, handleDeleteMessage, handleEditMessage } = useChatContext()
  const { activeSkill } = useUIContext()
  const bottomRef = useRef(null)
  const messagesRef = useRef(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [transparencyOpen, setTransparencyOpen] = useState(false)

  const isNearBottom = useRef(true)

  useEffect(() => {
    const container = messagesRef.current
    if (container && isNearBottom.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingText])

  useEffect(() => {
    const container = messagesRef.current
    if (!container) return
    const handleScroll = () => {
      const threshold = 150
      isNearBottom.current = container.scrollHeight - container.scrollTop - container.clientHeight < threshold
    }
    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (activeConversation && messages.length > 0) {
      setLoading(false)
    } else if (!activeConversation) {
      setLoading(false)
    }
  }, [activeConversation, messages])

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'f' && !e.shiftKey) {
        if (activeConversation) {
          e.preventDefault()
          setSearchOpen(prev => !prev)
        }
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [activeConversation])

  useEffect(() => {
    setSearchOpen(false)
  }, [activeConversation?.id])

  const showStreaming = streaming && streamingText
  const hasTransparency = (ragChunks && ragChunks.length > 0) || (activityLogs && activityLogs.length > 0)

  return (
    <main role="main" id="main-content" className="chat-panel">
      <SystemPromptBar activeSkill={activeSkill} />
      <div className="chat-panel-header">
        <TokenBar messages={messages} sessionId={activeConversation?.id} />
        {activeConversation && (
          <div className="chat-panel-actions">
            {hasTransparency && (
              <button
                className="toolbar-btn"
                onClick={() => setTransparencyOpen(!transparencyOpen)}
                title="Toggle transparency panel"
              >
                📊
              </button>
            )}
            <ConversationExport
              messages={messages}
              conversationTitle={activeConversation?.title}
            />
            <button
              className="toolbar-btn"
              onClick={() => setSearchOpen(!searchOpen)}
              title="Search in conversation (Ctrl+F)"
            >
              {searchOpen ? '✕' : '🔍'}
            </button>
          </div>
        )}
      </div>

      {searchOpen && (
        <ConversationSearch
          messages={messages}
          onClose={() => setSearchOpen(false)}
        />
      )}

      {transparencyOpen && hasTransparency && (
        <div className="chat-transparency">
          <RetrievedChunksPanel chunks={ragChunks} />
          <ToolActivityPanel logs={activityLogs} ragChunks={ragChunks} />
        </div>
      )}

      <div className="chat-messages" ref={messagesRef} role="log" aria-label="Chat messages" aria-live="polite">
        {!activeConversation ? (
          <div className="chat-empty">
            <h2>hiil</h2>
            <p>Start a conversation to begin. The AI can read and edit files in your workspace.</p>
          </div>
        ) : loading ? (
          <MessageSkeleton count={4} />
        ) : messages.length === 0 && !showStreaming ? (
          <div className="chat-empty">
            <h2>{activeConversation.title}</h2>
            <p>Ask a question or describe what you'd like to build.</p>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <MessageBubble
                key={msg.id || i}
                message={msg}
                onOpenFile={onOpenFile}
                onRetry={handleRetry}
                onDelete={handleDeleteMessage}
                onCopy={onCopy}
                onEdit={handleEditMessage}
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

      <ScrollToBottom containerRef={messagesRef} />
    </main>
  )
}
