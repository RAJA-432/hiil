import { getMockScenario } from '../config'
import { getMockMessages } from '../data/chats'
import { SCENARIO_CONFIG, ERROR_TYPES } from './scenarios'

function _randomDelay(cfg) {
  return cfg.delayMin + Math.random() * (cfg.delayMax - cfg.delayMin)
}

function _randomChunkSize(cfg, remaining) {
  return Math.min(cfg.chunkMin + Math.floor(Math.random() * (cfg.chunkMax - cfg.chunkMin + 1)), remaining)
}

export function simulateStreamResponse(convId, text, onEvent) {
  const cfg = SCENARIO_CONFIG[getMockScenario()]
  let i = 0
  let emitted = ''
  const toolCalls = []
  const mockChunks = [
    { text: 'Binary search trees support O(log n) insertion, deletion, and search operations on average.', score: 0.92, metadata: { filename: 'dsa_notes.md' } },
    { text: 'Python implementation of BST with insert, search, inorder traversal methods.', score: 0.87, metadata: { filename: 'examples/bst.py' } },
  ]
  let timer = null
  let resolveDone = null
  const done = new Promise((resolve) => { resolveDone = resolve })
  let cancelled = false
  let retryTimer = null

  function commitAssistantText() {
    const msgs = getMockMessages(convId)
    const last = msgs[msgs.length - 1]
    if (last && last.role === 'assistant') {
      last.content = emitted
    }
  }

  function emit() {
    if (cancelled) return

    if (i >= text.length) {
      commitAssistantText()
      if (onEvent) onEvent({ type: 'done', content: emitted })
      if (resolveDone) resolveDone()
      return
    }

    // Unreliable scenario: inject random errors mid-stream
    if (cfg.errorRate > 0 && Math.random() < cfg.errorRate && i > 10) {
      const err = ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)]
      onEvent({ type: 'mock_error', ...err })
      onEvent({ type: 'error', code: err.code || 500, message: err.message })

      // Simulate retry after delay
      if (cfg.retryDelay > 0) {
        onEvent({ type: 'log', level: 'warn', text: `Retrying after error (${err.type})...`, source: 'system' })
        retryTimer = setTimeout(() => {
          if (!cancelled) {
            onEvent({ type: 'log', level: 'info', text: 'Retry succeeded, continuing stream', source: 'system' })
            timer = setTimeout(emit, _randomDelay(cfg))
          }
        }, cfg.retryDelay)
      } else {
        commitAssistantText()
        if (resolveDone) resolveDone()
      }
      return
    }

    const chunkSize = _randomChunkSize(cfg, text.length - i)
    const chunk = text.slice(i, i + chunkSize)
    i += chunkSize
    emitted += chunk
    onEvent({ type: 'tokens', text: chunk })

    if (i > 30 && toolCalls.length === 0 && Math.random() < cfg.ragRate) {
      onEvent({ type: 'rag_context', chunks: mockChunks })
      onEvent({ type: 'log', level: 'info', text: 'Retrieved 2 chunks from knowledge base', source: 'rag' })
    }

    if (i > 30 && toolCalls.length === 0 && Math.random() < cfg.toolRate) {
      const tool = { tool: 'read_document', args: { path: 'src/main.py' }, status: 'running' }
      onEvent({ type: 'tool_event', tool: tool.tool, args: tool.args, status: tool.status, result: tool.result })
      const toolDelay = 300 + Math.random() * 400
      setTimeout(() => {
        if (!cancelled) {
          tool.status = 'done'
          tool.result = 'File contents loaded'
          onEvent({ type: 'tool_event', tool: tool.tool, args: tool.args, status: tool.status, result: tool.result })
          onEvent({ type: 'log', level: 'info', text: 'Tool read_document completed', source: 'tool' })
          toolCalls.push(tool)
        }
      }, toolDelay)
    }

    const delay = _randomDelay(cfg)
    timer = setTimeout(emit, delay)
  }

  emit()
  return {
    cancel: () => {
      cancelled = true
      if (timer) clearTimeout(timer)
      if (retryTimer) clearTimeout(retryTimer)
      if (resolveDone) resolveDone()
    },
    done,
  }
}
