import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('./mocks/config', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, USE_MOCK: true }
})

import { sendMessage } from './chat'
import { getMockMessages, setMockScenario } from './mocks'

describe('sendMessage mock mode', () => {
  beforeEach(() => {
    setMockScenario('fast')
  })

  it('commits the full assistant text when the stream completes', async () => {
    const events = []
    const stream = sendMessage('conv_1', 'Hi there', undefined, (e) => events.push(e), () => {})

    await stream.done

    const messages = getMockMessages('conv_1')
    const last = messages[messages.length - 1]
    expect(last.role).toBe('assistant')
    expect(last.content).not.toBe('')
    expect(last.content.length).toBeGreaterThan(0)
    expect(last.content.startsWith("I'll help you with that")).toBe(true)

    const doneEvent = events.find(e => e.type === 'done')
    expect(doneEvent).toBeDefined()
    expect(doneEvent.content).toBe(last.content)
  })
})
