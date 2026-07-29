import { describe, it, expect } from 'vitest'
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
