import { apiGet, apiPost, apiStream } from './client'
import { USE_MOCK, mockAgents, createMockAgent, findMockAgent, stopMockAgent, simulateAgentStream } from './mocks'

export async function listAgents() {
  if (USE_MOCK) return [...mockAgents]
  return (await apiGet('/api/agents')).agents || []
}

export async function createAgent(config) {
  if (USE_MOCK) return createMockAgent(config)
  return apiPost('/api/agents', config)
}

export async function getAgent(agentId) {
  if (USE_MOCK) return findMockAgent(agentId)
  return apiGet(`/api/agents/${agentId}`)
}

export function runAgent(agentId, input, onEvent, onError, signal) {
  if (USE_MOCK) {
    return simulateAgentStream(agentId, input, onEvent, onError, signal)
  }
  return apiStream('POST', `/api/agents/${agentId}/run`, { input }, onEvent, onError, signal)
}

export async function stopAgent(agentId) {
  if (USE_MOCK) return stopMockAgent(agentId)
  return apiPost(`/api/agents/${agentId}/stop`)
}

export async function resumeAgent(agentId, decisions) {
  if (USE_MOCK) return { status: 'completed', output: 'Mock resume completed' }
  return apiPost(`/api/agents/${agentId}/resume`, { decisions })
}
