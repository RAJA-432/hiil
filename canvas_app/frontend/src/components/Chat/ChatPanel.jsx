import { useEffect, useRef } from 'react'
import { marked } from './markdown'
import MessageBubble from './MessageBubble'

export default function ChatPanel({ messages, streaming, streamingText, activeConversation, onOpenFile }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const showStreaming = streaming && streamingText

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {!activeConversation ? (
          <div className="chat-empty">
            <h2>hiil</h2>
            <p>Start a conversation to begin. The AI can read and edit files in your workspace.</p>
          </div>
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
              />
            ))}
            {showStreaming && (
              <div className="message assistant">
                <div className="message-content">
                  <div dangerouslySetInnerHTML={{ __html: marked(streamingText) }} />
                  <span className="streaming-cursor" />
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
