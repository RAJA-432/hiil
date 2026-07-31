import { useState, useCallback, useRef, useEffect } from 'react'
import { listAgents, createAgent, runAgent, stopAgent, resumeAgent } from '../api/agents'

export function useAgents() {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [agentRun, setAgentRun] = useState(null)
  const [agentEvents, setAgentEvents] = useState([])
  const [agentRunning, setAgentRunning] = useState(false)
  const streamRef = useRef(null)

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listAgents()
      setAgents(data)
    } catch (err) {
      console.error('Failed to load agents:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleCreateAgent = useCallback(async (config) => {
    const agent = await createAgent(config)
    setAgents(prev => [...prev, agent])
    return agent
  }, [])

  const handleRunAgent = useCallback(async (agentId, input) => {
    setAgentRunning(true)
    setAgentEvents([])
    setAgentRun({ agentId, input })

    const onEvent = (event) => {
      setAgentEvents(prev => [...prev, event])
      if (event.type === 'interrupt') {
        setAgentRunning(false)
      }
    }

    const onError = (err) => {
      setAgentEvents(prev => [...prev, { type: 'error', message: err.message }])
      setAgentRunning(false)
    }

    try {
      const stream = runAgent(agentId, input, onEvent, onError)
      streamRef.current = stream
      await stream.done
    } catch (err) {
      if (err.name !== 'AbortError') {
        setAgentEvents(prev => [...prev, { type: 'error', message: err.message }])
      }
    } finally {
      setAgentRunning(false)
      streamRef.current = null
    }
  }, [])

  const handleStopAgent = useCallback(async (agentId) => {
    if (streamRef.current) {
      streamRef.current.cancel()
      streamRef.current = null
    }
    try {
      await stopAgent(agentId)
    } catch { }
    setAgentRunning(false)
    setAgents(prev => prev.map(a =>
      a.agent_id === agentId ? { ...a, status: 'idle' } : a
    ))
  }, [])

  const handleResumeAgent = useCallback(async (agentId, decisions) => {
    try {
      setAgentRunning(true)
      setAgentEvents(prev => [...prev, { type: 'log', level: 'info', text: 'Resuming agent...', source: 'agent' }])
      const result = await resumeAgent(agentId, decisions)
      setAgentEvents(prev => [...prev, { type: 'log', level: 'info', text: `Agent resumed: ${result.status}`, source: 'agent' }])
      if (result.status === 'completed') {
        setAgentEvents(prev => [...prev, { type: 'done' }])
      }
      setAgentRunning(false)
      loadAgents()
    } catch (err) {
      setAgentEvents(prev => [...prev, { type: 'error', message: err.message }])
      setAgentRunning(false)
    }
  }, [loadAgents])

  const handleCloseRun = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.cancel()
      streamRef.current = null
    }
    setAgentRun(null)
    setAgentEvents([])
    setAgentRunning(false)
    loadAgents()
  }, [loadAgents])

  return {
    agents, agentsLoading: loading,
    agentRun, agentEvents, agentRunning,
    loadAgents,
    createAgent: handleCreateAgent,
    runAgent: handleRunAgent,
    stopAgent: handleStopAgent,
    resumeAgent: handleResumeAgent,
    closeRun: handleCloseRun,
  }
}
