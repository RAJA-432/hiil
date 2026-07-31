import { MockScenario } from '../config'

export const SCENARIO_CONFIG = {
  [MockScenario.FAST]: {
    delayMin: 5,
    delayMax: 15,
    chunkMin: 5,
    chunkMax: 15,
    errorRate: 0,
    ragRate: 0.03,
    toolRate: 0.03,
    retryDelay: 0,
  },
  [MockScenario.NORMAL]: {
    delayMin: 15,
    delayMax: 45,
    chunkMin: 3,
    chunkMax: 10,
    errorRate: 0,
    ragRate: 0.05,
    toolRate: 0.05,
    retryDelay: 0,
  },
  [MockScenario.SLOW]: {
    delayMin: 80,
    delayMax: 200,
    chunkMin: 1,
    chunkMax: 4,
    errorRate: 0,
    ragRate: 0.08,
    toolRate: 0.08,
    retryDelay: 0,
  },
  [MockScenario.UNRELIABLE]: {
    delayMin: 20,
    delayMax: 150,
    chunkMin: 1,
    chunkMax: 8,
    errorRate: 0.12,
    ragRate: 0.06,
    toolRate: 0.06,
    retryDelay: 2000,
  },
}

export const ERROR_TYPES = [
  { type: 'error', code: 500, message: 'Internal server error. The model provider encountered an issue.' },
  { type: 'error', code: 429, message: 'Rate limit exceeded. Please wait before sending another request.' },
  { type: 'error', code: 503, message: 'Service temporarily unavailable. The upstream provider is experiencing high load.' },
  { type: 'error', code: 400, message: 'Bad request. The prompt was rejected by the content filter.' },
  { type: 'network', message: 'Connection lost. Check your network and try again.' },
  { type: 'timeout', message: 'Request timed out after 30s. The model took too long to respond.' },
]
