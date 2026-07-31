export const mockAgents = [
  { agent_id: 'agent_1', name: 'Data Analyst', role: 'Analyze data and create visualizations', capabilities: ['python', 'sql', 'charting'], status: 'idle' },
  { agent_id: 'agent_2', name: 'Code Reviewer', role: 'Review code for bugs and security issues', capabilities: ['code_review', 'security'], status: 'idle' },
  { agent_id: 'agent_3', name: 'Research Assistant', role: 'Gather information and synthesize findings', capabilities: ['search', 'summarization'], status: 'idle' },
]

let agentCounter = 4

export function createMockAgent(config) {
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

export function findMockAgent(agentId) {
  return mockAgents.find(a => a.agent_id === agentId) || null
}

export function stopMockAgent(agentId) {
  const agent = mockAgents.find(a => a.agent_id === agentId)
  if (agent) agent.status = 'idle'
  return { status: 'stopped' }
}
