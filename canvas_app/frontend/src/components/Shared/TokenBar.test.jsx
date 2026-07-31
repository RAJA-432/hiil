import { render, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import TokenBar from './TokenBar'

vi.mock('../../api/chat', () => ({
  fetchUsage: vi.fn(),
}))

import { fetchUsage } from '../../api/chat'

const messages = [{ content: 'hello' }]
const usage = (inT, outT) => ({
  session: { input_tokens: inT, output_tokens: outT, total_tokens: inT + outT, cost: 0.01 },
  total: { input_tokens: inT, output_tokens: outT, total_tokens: inT + outT, cost: 0.01 },
})

describe('TokenBar', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    fetchUsage.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches immediately on mount and debounces message-driven refetches', async () => {
    fetchUsage.mockResolvedValue(usage(100, 50))
    const { rerender } = render(<TokenBar messages={messages} sessionId="s1" />)
    expect(fetchUsage).toHaveBeenCalledTimes(1)
    expect(fetchUsage).toHaveBeenCalledWith('s1')

    rerender(<TokenBar messages={[...messages, { content: 'more' }]} sessionId="s1" />)
    rerender(<TokenBar messages={[...messages, { content: 'more' }, { content: 'again' }]} sessionId="s1" />)
    expect(fetchUsage).toHaveBeenCalledTimes(1)

    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    expect(fetchUsage).toHaveBeenCalledTimes(2)
  })

  it('fetches the new session immediately on switch and cancels the pending debounce', async () => {
    fetchUsage.mockResolvedValue(usage(100, 50))
    const { rerender } = render(<TokenBar messages={messages} sessionId="s1" />)
    expect(fetchUsage).toHaveBeenCalledTimes(1)

    rerender(<TokenBar messages={[...messages, { content: 'more' }]} sessionId="s1" />)
    expect(fetchUsage).toHaveBeenCalledTimes(1)

    rerender(<TokenBar messages={[...messages, { content: 'more' }]} sessionId="s2" />)
    expect(fetchUsage).toHaveBeenCalledTimes(2)
    expect(fetchUsage).toHaveBeenLastCalledWith('s2')

    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(fetchUsage).toHaveBeenCalledTimes(2)
  })

  it('does not apply a stale usage response after switching sessions', async () => {
    let resolveOld
    let resolveNew
    fetchUsage
      .mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
      .mockImplementationOnce(() => new Promise(resolve => { resolveNew = resolve }))

    const { rerender, getByText } = render(<TokenBar messages={messages} sessionId="s1" />)
    rerender(<TokenBar messages={[...messages, { content: 'more' }]} sessionId="s2" />)

    await act(async () => { resolveNew(usage(200, 200)) })
    await act(async () => { resolveOld(usage(999, 999)) })

    expect(getByText('in:200 out:200')).toBeInTheDocument()
  })
})
