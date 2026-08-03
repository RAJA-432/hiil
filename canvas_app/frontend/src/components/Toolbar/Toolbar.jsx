import { useState, useEffect, useCallback } from 'react'
import { useUIContext } from '../../context/UIContext'
import ModelPicker from './ModelPicker'
import ModelInfo from '../Shared/ModelInfo'
import ActiveSkill from '../Skills/ActiveSkill'

export default function Toolbar() {
  const { settings, updateSettings, models, activeModel, modelsLoading, activeSkill, toggleSidebar, togglePreview, selectedFile, handleSwitchModel, setSidebarView, setSettingsOpen, setShortcutsOpen, setConnectorsOpen } = useUIContext()
  const [connected, setConnected] = useState(navigator.onLine)

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch('/health', { method: 'GET', signal: AbortSignal.timeout(5000) })
      setConnected(res.ok)
    } catch {
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    const goOnline = () => { setConnected(true); checkHealth() }
    const goOffline = () => setConnected(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      clearInterval(interval)
    }
  }, [checkHealth])

  return (
    <header role="banner" style={{ gridArea: 'toolbar', display: 'flex', flexDirection: 'column' }}>
      <div className="toolbar">
        <button className="toolbar-btn toolbar-hamburger" onClick={toggleSidebar} aria-label="Open navigation menu">
          ☰
        </button>
        <span className="toolbar-brand">H.I.I.L.</span>

        <ModelPicker models={models} activeModel={activeModel} onSwitch={handleSwitchModel} loading={modelsLoading} />
        <ModelInfo model={activeModel} models={models} />
        <ActiveSkill skill={activeSkill} onClick={() => setSidebarView('skills')} />

        <div className="toolbar-spacer" />

        <button className="toolbar-btn" onClick={() => setConnectorsOpen(true)} aria-label="Manage connectors">
          🔌
        </button>
        <button className="toolbar-btn" onClick={() => setShortcutsOpen(true)} aria-label="Keyboard shortcuts (Ctrl+K)">
          ⌨
        </button>

        <button className="toolbar-btn" onClick={() => setSettingsOpen(true)} aria-label="Settings (Ctrl+,)">
          ⚙
        </button>

        {selectedFile && (
          <button className="toolbar-btn toolbar-hamburger" onClick={togglePreview} aria-label="Toggle preview">
            📄
          </button>
        )}

        <button
          className={`toolbar-btn ${settings.sidebarVisible ? 'active' : ''}`}
          onClick={() => updateSettings({ sidebarVisible: !settings.sidebarVisible })}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>

        <button
          className="toolbar-btn"
          onClick={() => updateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' })}
          aria-label="Toggle theme"
        >
          {settings.theme === 'dark' ? '☀' : '☾'}
        </button>
      </div>
      <footer className="status-bar">
        <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
        <span>{connected ? 'Connected' : 'Disconnected'}</span>
      </footer>
    </header>
  )
}
