import KaryaCall from './KaryaCall'
import { marked } from './markdown'

export default function MessageBubble({ message, onOpenFile }) {
  const { role, content, tool_calls: toolCalls, artifacts } = message

  const handleFileLink = (e) => {
    const link = e.target.closest('a[data-file]')
    if (link) {
      e.preventDefault()
      onOpenFile?.(link.dataset.file)
    }
  }

  return (
    <div className={`message ${role}`}>
      <div className="message-content" onClick={handleFileLink}>
        {role === 'assistant' ? (
          <div dangerouslySetInnerHTML={{ __html: marked(content) }} />
        ) : (
          content
        )}
      </div>

      {toolCalls?.length > 0 && (
        <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {toolCalls.map((tc, i) => (
            <KaryaCall key={i} toolCall={tc} onOpenFile={onOpenFile} />
          ))}
        </div>
      )}
    </div>
  )
}
