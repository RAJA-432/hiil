const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet, apiPost, apiStream } from './client'

const mockAgents = [
  { agent_id: 'agent_1', name: 'Data Analyst', role: 'Analyze data and create visualizations', capabilities: ['python', 'sql', 'charting'], status: 'idle' },
  { agent_id: 'agent_2', name: 'Code Reviewer', role: 'Review code for bugs and security issues', capabilities: ['code_review', 'security'], status: 'idle' },
  { agent_id: 'agent_3', name: 'Research Assistant', role: 'Gather information and synthesize findings', capabilities: ['search', 'summarization'], status: 'idle' },
]

let agentCounter = 4

export async function listAgents() {
  if (USE_MOCK) return [...mockAgents]
  return (await apiGet('/api/agents')).agents || []
}

export async function createAgent(config) {
  if (USE_MOCK) {
    const agent = {
      agent_id: `agent_${agentCounter++}`,
      name: config.name,
      role: config.role,
      capabilities: config.capabilities || [],
      status: 'idle',
    }
    mockAgents.push(agent)
    return agent
  }
  return apiPost('/api/agents', config)
}

export async function getAgent(agentId) {
  if (USE_MOCK) return mockAgents.find(a => a.agent_id === agentId) || null
  return apiGet(`/api/agents/${agentId}`)
}

export function runAgent(agentId, input, onEvent, onError, signal) {
  if (USE_MOCK) {
    return simulateAgentStream(agentId, input, onEvent, onError, signal)
  }
  return apiStream('POST', `/api/agents/${agentId}/run`, { input }, onEvent, onError, signal)
}

export async function stopAgent(agentId) {
  if (USE_MOCK) {
    const agent = mockAgents.find(a => a.agent_id === agentId)
    if (agent) agent.status = 'idle'
    return { status: 'stopped' }
  }
  return apiPost(`/api/agents/${agentId}/stop`)
}

export async function resumeAgent(agentId, decisions) {
  if (USE_MOCK) return { status: 'completed', output: 'Mock resume completed' }
  return apiPost(`/api/agents/${agentId}/resume`, { decisions })
}

async function* generateAgentEvents(agentId, input) {
  const cfg = { delayMin: 30, delayMax: 80, chunkMin: 3, chunkMax: 10 }

  yield { type: 'log', level: 'info', text: `Agent starting task: "${input.slice(0, 60)}..."`, source: 'agent' }

  const steps = [
    { text: 'Analyzing request...', delay: 200 },
    { text: 'Gathering context from workspace...', delay: 300 },
  ]
  for (const step of steps) {
    await new Promise(r => setTimeout(r, step.delay))
    yield { type: 'log', level: 'info', text: step.text, source: 'agent' }
  }

  yield { type: 'log', level: 'info', text: 'Calling LLM (iteration 1)...', source: 'agent' }
  await new Promise(r => setTimeout(r, 400))

  const reply = `I've analyzed the request and here are the results:

1. Found relevant files in the workspace
2. Applied the requested changes
3. Verified the output

## Summary

The task has been completed successfully. Here's what was done:

- **Analysis**: Reviewed the input and identified the key requirements
- **Execution**: Processed the task using available tools
- **Verification**: Confirmed the output meets the specifications`

  let buffer = ''
  for (let i = 0; i < reply.length; i += cfg.chunkMin + Math.floor(Math.random() * (cfg.chunkMax - cfg.chunkMin + 1))) {
    const chunk = reply.slice(i, i + cfg.chunkMin + Math.floor(Math.random() * (cfg.chunkMax - cfg.chunkMin + 1)))
    buffer += chunk
    yield { type: 'tokens', text: buffer }
    await new Promise(r => setTimeout(r, cfg.delayMin + Math.random() * (cfg.delayMax - cfg.delayMin)))
  }

  yield { type: 'log', level: 'info', text: 'Agent completed successfully.', source: 'agent' }
  yield { type: 'done' }
}

function simulateAgentStream(agentId, input, onEvent, onError, signal) {
  const controller = new AbortController()
  const donePromise = (async () => {
    const gen = generateAgentEvents(agentId, input)
    for await (const event of gen) {
      if (controller.signal.aborted || (signal && signal.aborted)) break
      if (onEvent) onEvent(event)
    }
  })()
  if (signal) signal.addEventListener('abort', () => controller.abort())
  return { cancel: () => controller.abort(), done: donePromise }
}
