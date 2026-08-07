import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
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
} from '../api/mocks'

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
      undefined,
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

describe('token throttling', () => {
  let rafQueue
  let emitEvent
  let resolveDone

  beforeEach(() => {
    rafQueue = []
    emitEvent = null
    resolveDone = null
    vi.stubGlobal('requestAnimationFrame', (cb) => {
      rafQueue.push(cb)
      return rafQueue.length
    })
    vi.stubGlobal('cancelAnimationFrame', () => {
      rafQueue = []
    })
    sendMessage.mockImplementation((cid, text, images, onEvent) => {
      emitEvent = onEvent
      return { done: new Promise((resolve) => { resolveDone = resolve }), cancel: vi.fn() }
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function flushFrames() {
    rafQueue.splice(0).forEach(cb => cb())
  }

  it('coalesces a burst of token events into one state update per frame', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    const sendPromise = result.current.send('Hello')
    await act(async () => {})
    expect(emitEvent).toBeDefined()

    await act(async () => {
      emitEvent({ type: 'tokens', text: 'Hel' })
      emitEvent({ type: 'tokens', text: 'lo ' })
      emitEvent({ type: 'tokens', text: 'world' })
    })
    expect(rafQueue).toHaveLength(1)
    expect(result.current.streamingText).toBe('')

    await act(async () => { flushFrames() })
    expect(result.current.streamingText).toBe('Hello world')

    await act(async () => {
      emitEvent({ type: 'tokens', text: '!' })
    })
    expect(rafQueue).toHaveLength(1)
    await act(async () => { flushFrames() })
    expect(result.current.streamingText).toBe('Hello world!')

    await act(async () => {
      resolveDone()
      await sendPromise
    })
  })

  it('flushes the final token batch at completion and drops stale flushes', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    const sendPromise = result.current.send('Hello')
    await act(async () => {})

    await act(async () => {
      emitEvent({ type: 'tokens', text: 'last' })
    })
    expect(result.current.streamingText).toBe('')

    await act(async () => {
      resolveDone()
      await sendPromise
    })
    expect(result.current.streamingText).toBe('')

    await act(async () => { flushFrames() })
    expect(result.current.streamingText).toBe('')
  })
})

describe('state phase events', () => {
  let emitEvent
  let resolveDone

  beforeEach(() => {
    emitEvent = null
    resolveDone = null
    sendMessage.mockImplementation((cid, text, images, onEvent) => {
      emitEvent = onEvent
      return { done: new Promise((resolve) => { resolveDone = resolve }), cancel: vi.fn() }
    })
  })

  it('collects state events into phases in arrival order', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    const sendPromise = result.current.send('Hello')
    await act(async () => {})
    expect(emitEvent).toBeDefined()

    await act(async () => {
      emitEvent({ type: 'state', agent_id: 'conv_1', phase: 'THINKING', timestamp: '2025-01-01T00:00:00Z', iteration: 1 })
      emitEvent({ type: 'state', agent_id: 'sub_1', phase: 'EXECUTING', timestamp: '2025-01-01T00:00:01Z', iteration: null })
    })
    expect(result.current.phases).toHaveLength(2)
    expect(result.current.phases[0]).toEqual({ agent_id: 'conv_1', phase: 'THINKING', timestamp: '2025-01-01T00:00:00Z', iteration: 1 })
    expect(result.current.phases[1]).toEqual({ agent_id: 'sub_1', phase: 'EXECUTING', timestamp: '2025-01-01T00:00:01Z', iteration: null })

    await act(async () => {
      emitEvent({ type: 'state', agent_id: 'conv_1', phase: 'DONE', timestamp: '2025-01-01T00:00:02Z', iteration: 1 })
    })
    expect(result.current.phases).toHaveLength(3)
    expect(result.current.phases[2].phase).toBe('DONE')

    await act(async () => {
      resolveDone()
      await sendPromise
    })
  })

  it('resets phases when a new run starts', async () => {
    const { result } = renderHook(() => useChat('conv_1'))

    const sendPromise = result.current.send('Hello')
    await act(async () => {})
    await act(async () => {
      emitEvent({ type: 'state', agent_id: 'conv_1', phase: 'THINKING', timestamp: '2025-01-01T00:00:00Z', iteration: 1 })
    })
    expect(result.current.phases).toHaveLength(1)

    await act(async () => {
      resolveDone()
      await sendPromise
    })

    const sendPromise2 = result.current.send('Again')
    await act(async () => {})
    expect(result.current.phases).toHaveLength(0)

    await act(async () => {
      emitEvent({ type: 'state', agent_id: 'conv_1', phase: 'EXECUTING', timestamp: '2025-01-01T00:00:03Z', iteration: 1 })
    })
    expect(result.current.phases).toHaveLength(1)
    expect(result.current.phases[0].phase).toBe('EXECUTING')

    await act(async () => {
      resolveDone()
      await sendPromise2
    })
  })
})
