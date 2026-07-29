import { useCallback } from 'react'

export default function ConversationExport({ messages, conversationTitle, onClose }) {
  const formatAsMarkdown = useCallback(() => {
    const lines = [`# ${conversationTitle || 'Conversation'}`, '', `_Exported on ${new Date().toLocaleString()}_`, '']
    for (const m of messages) {
      if (m.role === 'system') continue
      const role = m.role === 'user' ? '**You**' : '**Assistant**'
      lines.push(`### ${role}`, '', m.content || '', '')
      if (m.tool_calls?.length > 0) {
        for (const tc of m.tool_calls) {
          lines.push(`> 🛠 ${tc.tool} — ${tc.status}`, '')
        }
      }
      lines.push('---', '')
    }
    return lines.join('\n')
  }, [messages, conversationTitle])

  const formatAsJson = useCallback(() => {
    const data = {
      title: conversationTitle || 'Conversation',
      exported: new Date().toISOString(),
      message_count: messages.length,
      messages: messages.map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        tool_calls: m.tool_calls?.map(tc => ({ tool: tc.tool, status: tc.status })) || [],
      })),
    }
    return JSON.stringify(data, null, 2)
  }, [messages, conversationTitle])

  const handleExport = useCallback((format) => {
    const content = format === 'json' ? formatAsJson() : formatAsMarkdown()
    const ext = format === 'json' ? 'json' : 'md'
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${conversationTitle || 'conversation'}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
    onClose?.()
  }, [formatAsJson, formatAsMarkdown, conversationTitle, onClose])

  if (!messages || messages.length === 0) return null

  return (
    <div className="export-actions">
      <button className="toolbar-btn" onClick={() => handleExport('md')} title="Export as Markdown">
        Export MD
      </button>
      <button className="toolbar-btn" onClick={() => handleExport('json')} title="Export as JSON">
        Export JSON
      </button>
    </div>
  )
}
