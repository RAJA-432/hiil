import { apiGet, apiStream, apiPost } from './client'
import { USE_MOCK, getMockConversations, getMockMessages, addMockMessage, addMockConversation, deleteMockConversation, getMockUsage, simulateStreamResponse } from './mocks'

export function sendMessage(conversationId, message, images, onEvent, onError, signal) {
  if (USE_MOCK) {
    addMockMessage(conversationId, 'user', message, [], [])
    const reply =
      'I\'ll help you with that. Let me look into the relevant files first.\n\n```python\ndef example():\n    print("hello")\n```\n\nLet me know if you need any clarification.'
    addMockMessage(conversationId, 'assistant', '', [], [])
    return simulateStreamResponse(conversationId, reply, onEvent)
  }

  const body = { message, session_id: conversationId, stream: true }
  if (images?.length > 0) {
    body.images = images.map(i => i.dataUrl || i)
  }
  return apiStream('POST', `/api/chat?stream=1`, body, onEvent, onError, signal)
}

export async function loadConversations({ limit = 50, offset = 0 } = {}) {
  if (USE_MOCK) {
    const all = getMockConversations()
    return { conversations: all, total: all.length }
  }
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  const result = await apiGet(`/api/conversations?${params}`)
  return { conversations: result.conversations || [], total: result.total ?? result.conversations?.length ?? 0 }
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

export async function searchMessages(query) {
  if (USE_MOCK) {
    const q = query.toLowerCase()
    const allMessages = []
    const convs = getMockConversations()
    for (const conv of convs) {
      const msgs = getMockMessages(conv.id) || []
      for (const msg of msgs) {
        if ((msg.content || '').toLowerCase().includes(q)) {
          allMessages.push({
            conversation_id: conv.id,
            conversation_title: conv.title,
            message_id: msg.id,
            content: msg.content,
            snippet: (msg.content || '').slice(0, 200),
            timestamp: msg.timestamp,
          })
        }
      }
    }
    allMessages.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    return { results: allMessages.slice(0, 50), total_count: allMessages.length }
  }
  return apiGet(`/api/search?q=${encodeURIComponent(query)}`)
}

export async function sendFeedback(sessionId, rating, context = {}) {
  if (USE_MOCK) return { event_id: 'mock', total: rating === 1 ? 0.3 : -0.3 }
  return apiPost('/api/rewards', {
    session_id: sessionId,
    action_type: 'feedback',
    context: { rating, ...context },
  })
}

export async function fetchUsage() {
  if (USE_MOCK) return getMockUsage()
  try {
    const resp = await apiGet('/api/usage')
    return resp || { session: null, total: null }
  } catch {
    return { session: null, total: null }
  }
}
