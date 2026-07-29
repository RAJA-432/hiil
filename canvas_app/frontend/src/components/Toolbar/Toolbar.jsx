import ModelPicker from './ModelPicker'
import ModelInfo from '../Shared/ModelInfo'
import ActiveSkill from '../Skills/ActiveSkill'

export default function Toolbar({ brand, activeModel, models, onSwitchModel, sidebarVisible, onToggleSidebar, settings, onUpdateSettings, onOpenSettings, onOpenShortcuts, activeSkill, onOpenSkills, onOpenConnectors }) {
  return (
    <div className="toolbar">
      <span className="toolbar-brand">{brand}</span>

      <ModelPicker models={models} activeModel={activeModel} onSwitch={onSwitchModel} />
      <ModelInfo model={activeModel} models={models} />
      <ActiveSkill skill={activeSkill} onClick={onOpenSkills} />

      <div className="toolbar-spacer" />

      <button className="toolbar-btn" onClick={onOpenConnectors} aria-label="Manage connectors">
        🔌
      </button>
      <button className="toolbar-btn" onClick={onOpenShortcuts} aria-label="Keyboard shortcuts (Ctrl+K)">
        ⌨
      </button>

      <button className="toolbar-btn" onClick={onOpenSettings} aria-label="Settings (Ctrl+,)">
        ⚙
      </button>

      <button
        className={`toolbar-btn ${sidebarVisible ? 'active' : ''}`}
        onClick={onToggleSidebar}
        aria-label="Toggle sidebar"
      >
        ☰
      </button>

      <button
        className="toolbar-btn"
        onClick={() => onUpdateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' })}
        aria-label="Toggle theme"
      >
        {settings.theme === 'dark' ? '☀' : '☾'}
      </button>
    </div>
  )
}
