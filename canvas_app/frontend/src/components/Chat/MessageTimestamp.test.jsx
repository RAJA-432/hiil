import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import MessageTimestamp from './MessageTimestamp'

describe('MessageTimestamp', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-01-15T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders "just now" for current timestamp', () => {
    render(<MessageTimestamp timestamp="2025-01-15T12:00:00Z" />)
    expect(screen.getByText('Just now')).toBeInTheDocument()
  })

  it('renders "just now" for timestamps within a minute', () => {
    render(<MessageTimestamp timestamp="2025-01-15T11:59:30Z" />)
    expect(screen.getByText('Just now')).toBeInTheDocument()
  })

  it('renders "Xm ago" for timestamps within an hour', () => {
    render(<MessageTimestamp timestamp="2025-01-15T11:30:00Z" />)
    expect(screen.getByText('30m ago')).toBeInTheDocument()
  })

  it('renders date string for older timestamps', () => {
    render(<MessageTimestamp timestamp="2025-01-10T12:00:00Z" />)
    expect(screen.getByText('5d ago')).toBeInTheDocument()
  })
})
