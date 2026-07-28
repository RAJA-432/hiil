const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet, apiStream, apiPost, apiDelete } from './client'
import { getMockConversations, getMockMessages, addMockMessage, simulateStreamResponse } from './mock'

export async function sendMessage(conversationId, message, onEvent, onError, signal) {
  if (USE_MOCK) {
    addMockMessage(conversationId, 'user', message, [], [])
    const reply =
      'I\'ll help you with that. Let me look into the relevant files first.\n\n```python\ndef example():\n    print("hello")\n```\n\nLet me know if you need any clarification.'
    let token = ''
    addMockMessage(conversationId, 'assistant', '', [], [])
    return simulateStreamResponse(conversationId, reply,
      (text) => { token = text; onEvent({ type: 'tokens', text }) },
      (tool) => onEvent({ type: 'tool_event', tool: tool.tool, args: tool.args, status: tool.status, result: tool.result }),
      (final, toolCalls, artifacts) => {
        const msgs = getMockMessages(conversationId)
        const last = msgs[msgs.length - 1]
        if (last) last.content = final
      },
    )
  }

  return apiStream('POST', `/api/chat?stream=1`, { message, session_id: conversationId, stream: true }, onEvent, onError, signal)
}

export async function loadConversations() {
  if (USE_MOCK) return getMockConversations()
  return (await apiGet('/api/conversations')).conversations || []
}

export async function loadConversationMessages(conversationId) {
  if (USE_MOCK) return getMockMessages(conversationId)
  return (await apiGet(`/api/history/${conversationId}`)).messages || []
}

export async function createConversation() {
  if (USE_MOCK) return addMockConversation()
  return (await apiPost('/api/session/new')).session_id
}

export async function deleteConversation(id) {
  if (USE_MOCK) return deleteMockConversation(id)
  return apiPost('/api/session/delete', { session_id: id })
}

export async function renameConversation(id, title) {
  if (USE_MOCK) {
    const conv = getMockConversations().find(c => c.id === id)
    if (conv) conv.title = title
    return true
  }
  return apiPost('/api/session/rename', { session_id: id, new_title: title })
}
