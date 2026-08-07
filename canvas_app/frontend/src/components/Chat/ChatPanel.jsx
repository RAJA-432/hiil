import { useEffect, useRef, useState } from 'react'
import { useChatContext } from '../../context/ChatContext'
import { useUIContext } from '../../context/UIContext'
import WindowedMessageList from './WindowedMessageList'
import TokenBar from '../Shared/TokenBar'
import RetrievedChunksPanel from './RetrievedChunksPanel'
import ToolActivityPanel from './ToolActivityPanel'
import ScrollToBottom from '../Shared/ScrollToBottom'
import ConversationSearch from './ConversationSearch'
import ConversationExport from '../Shared/ConversationExport'
import SystemPromptBar from './SystemPromptBar'

export default function ChatPanel({ onOpenFile, onCopy }) {
  const { messages, streaming, streamingText, ragChunks, activityLogs, phases, error, activeConversation, scrollToMessageId, handleRetry, handleDeleteMessage, handleEditMessage } = useChatContext()
  const { activeSkill } = useUIContext()
  const bottomRef = useRef(null)
  const messagesRef = useRef(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [transparencyOpen, setTransparencyOpen] = useState(false)

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
  const hasTransparency = (ragChunks && ragChunks.length > 0) || (activityLogs && activityLogs.length > 0) || (phases && phases.length > 0)

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
          <ToolActivityPanel logs={activityLogs} ragChunks={ragChunks} phases={phases} />
        </div>
      )}

      <WindowedMessageList
        messages={messages}
        streamingText={streamingText}
        showStreaming={showStreaming}
        error={error}
        loading={loading}
        activeConversation={activeConversation}
        scrollToMessageId={scrollToMessageId}
        containerRef={messagesRef}
        bottomRef={bottomRef}
        onOpenFile={onOpenFile}
        onRetry={handleRetry}
        onDelete={handleDeleteMessage}
        onCopy={onCopy}
        onEdit={handleEditMessage}
      />

      <ScrollToBottom containerRef={messagesRef} />
    </main>
  )
}
