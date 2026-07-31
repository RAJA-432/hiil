import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import {
  getMockUsage,
  getMockConversations,
  getMockMessages,
  getMockFileTree,
  getMockFileContent,
  getMockModels,
  addMockMessage,
  addMockConversation,
  deleteMockConversation,
  simulateStreamResponse,
} from '../api/mock'

vi.mock('../api/chat', () => ({
  sendMessage: vi.fn(() => ({
    done: Promise.resolve(),
    cancel: vi.fn(),
  })),
  loadConversationMessages: vi.fn(() => Promise.resolve([])),
}))

import { useChat } from './useChat'
import { sendMessage, loadConversationMessages } from '../api/chat'

describe('mock module', () => {
  it('exports all expected functions', () => {
    expect(getMockUsage).toBeDefined()
    expect(getMockConversations).toBeDefined()
    expect(getMockMessages).toBeDefined()
    expect(getMockFileTree).toBeDefined()
    expect(getMockFileContent).toBeDefined()
    expect(getMockModels).toBeDefined()
    expect(addMockMessage).toBeDefined()
    expect(addMockConversation).toBeDefined()
    expect(deleteMockConversation).toBeDefined()
    expect(simulateStreamResponse).toBeDefined()
  })

  it('getMockUsage returns the right shape', () => {
    const usage = getMockUsage()

    expect(usage).toHaveProperty('session')
    expect(usage).toHaveProperty('total')

    expect(usage.session).toHaveProperty('input_tokens')
    expect(usage.session).toHaveProperty('output_tokens')
    expect(usage.session).toHaveProperty('total_tokens')
    expect(usage.session).toHaveProperty('cost')

    expect(usage.total).toHaveProperty('input_tokens')
    expect(usage.total).toHaveProperty('output_tokens')
    expect(usage.total).toHaveProperty('total_tokens')
    expect(usage.total).toHaveProperty('cost')

    expect(typeof usage.session.input_tokens).toBe('number')
    expect(typeof usage.session.output_tokens).toBe('number')
    expect(typeof usage.session.total_tokens).toBe('number')
    expect(typeof usage.session.cost).toBe('number')

    expect(typeof usage.total.input_tokens).toBe('number')
    expect(typeof usage.total.output_tokens).toBe('number')
    expect(typeof usage.total.total_tokens).toBe('number')
    expect(typeof usage.total.cost).toBe('number')
  })
})

describe('useChat hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('send() calls the API with correct params', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    await act(async () => {
      await result.current.send('Test message')
    })

    expect(sendMessage).toHaveBeenCalledWith(
      'conv_1',
      'Test message',
      expect.any(Function),
      expect.any(Function),
      expect.any(AbortSignal),
    )
    expect(loadConversationMessages).toHaveBeenCalledWith('conv_1')
  })

  it('deleteMessage() removes a message', () => {
    const { result } = renderHook(() => useChat('conv_1'))

    act(() => {
      result.current.setMessages([{ id: 'msg1', role: 'user', content: 'Hello', timestamp: new Date().toISOString() }])
    })

    expect(result.current.messages).toHaveLength(1)

    act(() => {
      result.current.deleteMessage('msg1')
    })

    expect(result.current.messages).toHaveLength(0)
  })

  it('editMessage() replaces message content', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    act(() => {
      result.current.setMessages([
        { id: 'm1', role: 'user', content: 'Old text', timestamp: new Date().toISOString() },
      ])
    })

    const msg = result.current.messages[0]

    await act(async () => {
      await result.current.editMessage(msg, 'New text')
    })

    expect(sendMessage).toHaveBeenCalled()
    expect(result.current.messages.find(m => m.id === 'm1')).toBeUndefined()
  })
})
