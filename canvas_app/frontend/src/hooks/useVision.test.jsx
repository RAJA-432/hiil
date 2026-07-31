import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

const mockApiStream = vi.fn(() => ({
  cancel: vi.fn(),
  done: Promise.resolve(),
}))

vi.mock('../api/client', () => ({
  apiStream: (...args) => mockApiStream(...args),
}))

import { sendMessage } from '../api/chat'
import { useChat } from './useChat'

describe('sendMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sends images as separate field when images are provided', () => {
    const onEvent = vi.fn()
    const onError = vi.fn()
    const signal = new AbortController().signal
    const images = ['data:image/png;base64,abc123']

    sendMessage('conv_1', 'Describe this', images, onEvent, onError, signal)

    expect(mockApiStream).toHaveBeenCalledWith(
      'POST',
      '/api/chat?stream=1',
      expect.objectContaining({
        message: 'Describe this',
        session_id: 'conv_1',
        stream: true,
        images: ['data:image/png;base64,abc123'],
      }),
      onEvent,
      onError,
      signal,
    )
  })

  it('does NOT include images field when no images', () => {
    const onEvent = vi.fn()
    const onError = vi.fn()
    const signal = new AbortController().signal

    sendMessage('conv_1', 'Hello', undefined, onEvent, onError, signal)

    expect(mockApiStream).toHaveBeenCalledWith(
      'POST',
      '/api/chat?stream=1',
      { message: 'Hello', session_id: 'conv_1', stream: true },
      onEvent,
      onError,
      signal,
    )
  })
})

describe('runStream', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('passes images through to the API', async () => {
    const { result } = renderHook(() => useChat('conv_1'))
    const images = ['data:image/png;base64,abc123']

    await act(async () => {
      await result.current.send('Analyze this', images)
    })

    expect(mockApiStream).toHaveBeenCalledWith(
      'POST',
      '/api/chat?stream=1',
      expect.objectContaining({ images: ['data:image/png;base64,abc123'] }),
      expect.any(Function),
      expect.any(Function),
      expect.any(AbortSignal),
    )
  })
})
