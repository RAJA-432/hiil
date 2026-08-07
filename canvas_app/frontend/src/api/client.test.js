import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiStream } from './client'

function streamResponseFromLines(lines) {
  const encoder = new TextEncoder()
  return {
    ok: true,
    body: new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(lines.join('\n')))
        controller.close()
      },
    }),
  }
}

describe('apiStream', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('parses newline-delimited JSON lines and emits tokens/done/tool_event events', async () => {
    const events = []
    fetch.mockResolvedValue(streamResponseFromLines([
      '{"type":"tokens","text":"Hel"}',
      '{"type":"tokens","text":"lo"}',
      '{"type":"tool_event","tool":"read_document","status":"done"}',
      '{"type":"done"}',
    ]))

    const { done } = apiStream('POST', '/api/chat', { message: 'hi' }, (e) => events.push(e))
    await done

    expect(fetch).toHaveBeenCalledWith(
      '/api/chat',
      expect.objectContaining({ method: 'POST', body: '{"message":"hi"}' }),
    )
    expect(events).toEqual([
      { type: 'tokens', text: 'Hel' },
      { type: 'tokens', text: 'lo' },
      { type: 'tool_event', tool: 'read_document', status: 'done' },
      { type: 'done' },
    ])
  })

  it('skips empty lines and handles a trailing newline', async () => {
    const events = []
    fetch.mockResolvedValue(streamResponseFromLines([
      '',
      '{"type":"tokens","text":"a"}',
      '',
      '{"type":"tokens","text":"b"}',
      '',
    ]))

    const { done } = apiStream('POST', '/api/chat', {}, (e) => events.push(e))
    await done

    expect(events).toEqual([
      { type: 'tokens', text: 'a' },
      { type: 'tokens', text: 'b' },
    ])
  })

  it('buffers JSON lines split across multiple stream reads', async () => {
    const events = []
    const encoder = new TextEncoder()
    fetch.mockResolvedValue({
      ok: true,
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(encoder.encode('{"type":"tokens","tex'))
          controller.enqueue(encoder.encode('t":"He"}'))
          controller.enqueue(encoder.encode('\n{"type":"done"}\n'))
          controller.close()
        },
      }),
    })

    const { done } = apiStream('POST', '/api/chat', {}, (e) => events.push(e))
    await done

    expect(events).toEqual([
      { type: 'tokens', text: 'He' },
      { type: 'done' },
    ])
  })

  it('skips malformed JSON lines without failing the stream', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const events = []
    fetch.mockResolvedValue(streamResponseFromLines([
      '{not valid json',
      '{"type":"done"}',
    ]))

    const { done } = apiStream('POST', '/api/chat', {}, (e) => events.push(e))
    await done

    expect(events).toEqual([{ type: 'done' }])
    expect(warn).toHaveBeenCalledTimes(1)
  })
})
