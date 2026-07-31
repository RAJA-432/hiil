import { useState, useCallback, useRef } from 'react'

let toastId = 0

export function useToast() {
  const [toasts, setToasts] = useState([])
  const timersRef = useRef({})

  const remove = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    clearTimeout(timersRef.current[id])
    delete timersRef.current[id]
  }, [])

  const add = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId
    setToasts(prev => {
      if (prev.some(t => t.message === message && t.type === type)) return prev
      timersRef.current[id] = setTimeout(() => remove(id), duration)
      return [...prev, { id, message, type }]
    })
    return id
  }, [remove])

  const success = useCallback((msg, dur) => add(msg, 'success', dur), [add])
  const error = useCallback((msg, dur) => add(msg, 'error', dur), [add])
  const info = useCallback((msg, dur) => add(msg, 'info', dur), [add])

  return { toasts, add, remove, success, error, info }
}
