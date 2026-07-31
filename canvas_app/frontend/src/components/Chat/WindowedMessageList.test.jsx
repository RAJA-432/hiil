import { createRef } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import WindowedMessageList from './WindowedMessageList'

vi.mock('./MessageBubble', () => ({
  default: ({ message }) => <div data-testid="bubble">{message.id}</div>,
}))

function makeMessages(count) {
  return Array.from({ length: count }, (_, i) => ({
    id: `m${i}`,
    role: i % 2 === 0 ? 'user' : 'assistant',
    content: `Message ${i}`,
    timestamp: new Date(Date.UTC(2025, 0, 1, 0, 0, i)).toISOString(),
    tool_calls: [],
  }))
}

function baseProps(messages) {
  return {
    messages,
    streamingText: '',
    showStreaming: false,
    error: null,
    loading: false,
    activeConversation: { id: 'conv_1', title: 'Test' },
    scrollToMessageId: null,
    containerRef: createRef(),
    bottomRef: createRef(),
    onOpenFile: () => {},
    onRetry: () => {},
    onDelete: () => {},
    onCopy: () => {},
    onEdit: () => {},
  }
}

describe('WindowedMessageList', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('renders only a bounded window of the newest messages', () => {
    render(<WindowedMessageList {...baseProps(makeMessages(250))} />)
    expect(screen.getAllByTestId('bubble')).toHaveLength(100)
    expect(screen.queryByText('m0')).not.toBeInTheDocument()
    expect(screen.getByText('m249')).toBeInTheDocument()
  })

  it('loads an older chunk when scrolled to the top', () => {
    const props = baseProps(makeMessages(250))
    render(<WindowedMessageList {...props} />)
    expect(screen.getAllByTestId('bubble')).toHaveLength(100)
    fireEvent.scroll(props.containerRef.current)
    expect(screen.getAllByTestId('bubble')).toHaveLength(150)
    expect(screen.getByText('m100')).toBeInTheDocument()
  })

  it('keeps the window pinned to the newest messages as they arrive', () => {
    const props = baseProps(makeMessages(100))
    const { rerender } = render(<WindowedMessageList {...props} />)
    expect(screen.getAllByTestId('bubble')).toHaveLength(100)
    props.messages = makeMessages(150)
    rerender(<WindowedMessageList {...props} />)
    expect(screen.getAllByTestId('bubble')).toHaveLength(100)
    expect(screen.getByText('m149')).toBeInTheDocument()
  })

  it('reveals a searched message that is outside the current window', () => {
    const props = baseProps(makeMessages(250))
    props.scrollToMessageId = 'm10'
    render(<WindowedMessageList {...props} />)
    expect(screen.getByText('m10')).toBeInTheDocument()
  })
})
