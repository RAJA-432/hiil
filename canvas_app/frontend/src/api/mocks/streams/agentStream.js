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

  for (let i = 0; i < reply.length; i += cfg.chunkMin + Math.floor(Math.random() * (cfg.chunkMax - cfg.chunkMin + 1))) {
    const chunk = reply.slice(i, i + cfg.chunkMin + Math.floor(Math.random() * (cfg.chunkMax - cfg.chunkMin + 1)))
    yield { type: 'tokens', text: chunk }
    await new Promise(r => setTimeout(r, cfg.delayMin + Math.random() * (cfg.delayMax - cfg.delayMin)))
  }

  yield { type: 'log', level: 'info', text: 'Agent completed successfully.', source: 'agent' }
  yield { type: 'done' }
}

export function simulateAgentStream(agentId, input, onEvent, onError, signal) {
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

export { generateAgentEvents }
