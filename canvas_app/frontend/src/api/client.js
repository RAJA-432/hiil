const BACKEND_URL = ''

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `HTTP ${status}`)
    this.status = status
  }
}

export async function apiGet(path) {
  const res = await fetch(`${BACKEND_URL}${path}`)
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

export async function apiPost(path, body) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

export async function apiDelete(path) {
  const res = await fetch(`${BACKEND_URL}${path}`, { method: 'DELETE' })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

export function apiStream(method, path, body, onEvent, onError, signal) {
  const controller = new AbortController()
  const internalSignal = controller.signal

  // Combine external signal with internal controller
  const abortSignal = signal
    ? AbortSignal.any([signal, internalSignal])
    : internalSignal

  fetch(`${BACKEND_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: abortSignal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const detail = await res.text().catch(() => '')
        if (onError) onError(new ApiError(res.status, detail))
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue
          try {
            const event = JSON.parse(trimmed)
            if (onEvent) onEvent(event)
          } catch (e) {
            console.warn('Failed to parse SSE event:', e)
          }
        }
      }
      return 'ok';
    })
    .catch((err) => {
      if (onError && err.name !== 'AbortError') onError(err)
    })

  return {
    cancel: () => controller.abort(),
  }
}
