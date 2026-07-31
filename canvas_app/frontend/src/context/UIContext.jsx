import { createContext, useContext, useState, useCallback } from 'react'
import { useSettings } from '../hooks/useSettings'
import { useAppState } from '../hooks/useAppState'
import { useAgents } from '../hooks/useAgents'

const UIContext = createContext(null)

export function UIProvider({ children }) {
  const { settings, update: updateSettings } = useSettings()
  const [sidebarView, setSidebarView] = useState('conversations')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const [connectorsOpen, setConnectorsOpen] = useState(false)
  const [tourOpen, setTourOpen] = useState(() => {
    try { return localStorage.getItem('hiil_tour_complete') !== 'true' } catch { return true }
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [agentCreateOpen, setAgentCreateOpen] = useState(false)
  const [agentToRun, setAgentToRun] = useState(null)

  const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), [])
  const togglePreview = useCallback(() => setPreviewOpen(prev => !prev), [])

  const appState = useAppState(settings.model)
  const agentState = useAgents()

  const value = {
    settings, updateSettings,
    sidebarView, setSidebarView,
    settingsOpen, setSettingsOpen,
    shortcutsOpen, setShortcutsOpen,
    connectorsOpen, setConnectorsOpen,
    tourOpen, setTourOpen,
    sidebarOpen, setSidebarOpen, toggleSidebar,
    previewOpen, setPreviewOpen, togglePreview,
    agentCreateOpen, setAgentCreateOpen,
    agentToRun, setAgentToRun,
    ...appState,
    ...agentState,
  }

  return <UIContext.Provider value={value}>{children}</UIContext.Provider>
}

export function useUIContext() {
  const ctx = useContext(UIContext)
  if (!ctx) throw new Error('useUIContext must be used within UIProvider')
  return ctx
}
