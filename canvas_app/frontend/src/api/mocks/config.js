export const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

export const MockScenario = {
  /** Fast: no errors, minimal delay (default). */
  FAST: 'fast',
  /** Normal: typical latency, occasional RAG events. */
  NORMAL: 'normal',
  /** Slow: high latency, throttled output. */
  SLOW: 'slow',
  /** Unreliable: random errors, retries, high latency spikes. */
  UNRELIABLE: 'unreliable',
}

let _activeScenario = MockScenario.NORMAL

export function setMockScenario(scenario) {
  if (MockScenario[scenario] || Object.values(MockScenario).includes(scenario)) {
    _activeScenario = scenario
  }
}

export function getMockScenario() {
  return _activeScenario
}
