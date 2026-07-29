import { useState, useCallback, useRef } from 'react'

export function useUndo() {
  const [undoItems, setUndoItems] = useState([])
  const timersRef = useRef({})

  const push = useCallback((item, timeout = 5000) => {
    const id = `undo-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const entry = { id, ...item }
    setUndoItems(prev => [...prev, entry])
    timersRef.current[id] = setTimeout(() => {
      setUndoItems(prev => prev.filter(i => i.id !== id))
    }, timeout)
    return id
  }, [])

  const dismiss = useCallback((id) => {
    setUndoItems(prev => prev.filter(i => i.id !== id))
    clearTimeout(timersRef.current[id])
    delete timersRef.current[id]
  }, [])

  const clear = useCallback(() => {
    Object.values(timersRef.current).forEach(clearTimeout)
    timersRef.current = {}
    setUndoItems([])
  }, [])

  return { undoItems, push, dismiss, clear }
}
