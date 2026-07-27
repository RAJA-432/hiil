import { useState, useCallback } from 'react'
import { loadUIState, saveUIState } from '../stores/ui'

export function useSettings() {
  const [settings, setSettings] = useState(loadUIState)

  const update = useCallback((patch) => {
    setSettings(prev => {
      const next = { ...prev, ...patch }
      saveUIState(next)
      return next
    })
  }, [])

  return { settings, update }
}
