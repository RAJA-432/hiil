import { useState, useEffect } from 'react'
import { useUIContext } from '../../context/UIContext'
import Modal from './Modal'

export default function SettingsModal() {
  const { settings, updateSettings, models, activeModel, handleSwitchModel, settingsOpen, setSettingsOpen } = useUIContext()
  const [systemPrompt, setSystemPrompt] = useState(settings.systemPrompt || '')
  const [temperature, setTemperature] = useState(settings.temperature ?? 0.7)
  const [maxTokens, setMaxTokens] = useState(settings.maxTokens ?? 4096)
  const [apiBaseUrl, setApiBaseUrl] = useState(settings.apiBaseUrl || '')
  const [apiKey, setApiKey] = useState(settings.apiKey || '')
  const [showApiKey, setShowApiKey] = useState(false)

  useEffect(() => {
    setSystemPrompt(settings.systemPrompt || '')
    setTemperature(settings.temperature ?? 0.7)
    setMaxTokens(settings.maxTokens ?? 4096)
    setApiBaseUrl(settings.apiBaseUrl || '')
    setApiKey(settings.apiKey || '')
  }, [settings])
  const [saving, setSaving] = useState(false)

  const handleSave = () => {
    if (saving) return
    setSaving(true)
    updateSettings({
      systemPrompt,
      temperature: parseFloat(temperature),
      maxTokens: parseInt(maxTokens, 10) || 4096,
      apiBaseUrl,
      apiKey,
    })
    setSettingsOpen(false)
  }

  return (
    <Modal open={settingsOpen} onClose={() => setSettingsOpen(false)} title="Settings" width={560}>
      <div className="settings-form">
        <div className="settings-section">
          <label className="settings-label" htmlFor="settings-model-select">Model</label>
          <select
            id="settings-model-select"
            className="settings-select"
            value={activeModel}
            onChange={e => handleSwitchModel(e.target.value)}
          >
            {models.map(m => (
              <option key={m.id || m} value={m.id || m}>{m.name || m.id || m}</option>
            ))}
          </select>
        </div>

        <div className="settings-section">
          <label className="settings-label">Temperature</label>
          <div className="settings-range-row">
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              value={temperature}
              onChange={e => setTemperature(e.target.value)}
              className="settings-range"
            />
            <span className="settings-range-value">{temperature}</span>
          </div>
        </div>

        <div className="settings-section">
          <label className="settings-label">Max Tokens</label>
          <input
            type="number"
            className="settings-input"
            value={maxTokens}
            onChange={e => setMaxTokens(e.target.value)}
            min={256}
            max={128000}
            step={256}
          />
        </div>

        <div className="settings-section">
          <label className="settings-label">API Base URL</label>
          <input
            type="text"
            className="settings-input"
            value={apiBaseUrl}
            onChange={e => setApiBaseUrl(e.target.value)}
            placeholder="http://localhost:11434/v1"
          />
        </div>

        <div className="settings-section">
          <label className="settings-label">API Key</label>
          <div className="settings-password-row">
            <input
              type={showApiKey ? 'text' : 'password'}
              className="settings-input"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              placeholder="sk-..."
            />
            <button
              className="toolbar-btn"
              onClick={() => setShowApiKey(!showApiKey)}
              title={showApiKey ? 'Hide' : 'Show'}
            >
              {showApiKey ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        <div className="settings-section">
          <label className="settings-label">System Prompt</label>
          <textarea
            className="settings-textarea"
            value={systemPrompt}
            onChange={e => setSystemPrompt(e.target.value)}
            rows={6}
            placeholder="You are a helpful assistant..."
          />
        </div>

        <div className="settings-actions">
          <button className="toolbar-btn" onClick={() => setSettingsOpen(false)}>Cancel</button>
          <button className="settings-save-btn" onClick={handleSave} disabled={saving}>{saving ? 'Saving…' : 'Save Settings'}</button>
        </div>
      </div>
    </Modal>
  )
}
