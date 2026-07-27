import ModelPicker from './ModelPicker'

export default function Toolbar({ brand, activeModel, models, onSwitchModel, sidebarVisible, previewVisible, onToggleSidebar, settings, onUpdateSettings }) {
  return (
    <div className="toolbar">
      <span className="toolbar-brand">{brand}</span>

      <ModelPicker models={models} activeModel={activeModel} onSwitch={onSwitchModel} />

      <div className="toolbar-spacer" />

      <button
        className={`toolbar-btn ${sidebarVisible ? 'active' : ''}`}
        onClick={onToggleSidebar}
        title="Toggle sidebar"
      >
        ☰
      </button>

      <button
        className="toolbar-btn"
        onClick={() => onUpdateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' })}
        title="Toggle theme"
      >
        {settings.theme === 'dark' ? '☀' : '☾'}
      </button>
    </div>
  )
}
