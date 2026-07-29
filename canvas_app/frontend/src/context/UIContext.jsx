import { createContext, useContext, useState, useCallback } from 'react'
import { useSettings } from '../hooks/useSettings'
import { useAppState } from '../hooks/useAppState'

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

  const toggleSidebar = useCallback(() => setSidebarOpen(prev => !prev), [])
  const togglePreview = useCallback(() => setPreviewOpen(prev => !prev), [])

  const appState = useAppState(settings.model)

  const value = {
    settings, updateSettings,
    sidebarView, setSidebarView,
    settingsOpen, setSettingsOpen,
    shortcutsOpen, setShortcutsOpen,
    connectorsOpen, setConnectorsOpen,
    tourOpen, setTourOpen,
    sidebarOpen, setSidebarOpen, toggleSidebar,
    previewOpen, setPreviewOpen, togglePreview,
    ...appState,
  }

  return <UIContext.Provider value={value}>{children}</UIContext.Provider>
}

export function useUIContext() {
  const ctx = useContext(UIContext)
  if (!ctx) throw new Error('useUIContext must be used within UIProvider')
  return ctx
}
