const UI_STORE_KEY = 'hiil_ui_state'

const defaults = {
  theme: 'dark',
  sidebarWidth: 260,
  previewWidth: 480,
  sidebarVisible: true,
  previewVisible: true,
  model: 'gpt-4o-mini',
}

export function loadUIState() {
  try {
    const raw = localStorage.getItem(UI_STORE_KEY)
    if (raw) return { ...defaults, ...JSON.parse(raw) }
  } catch {}
  return { ...defaults }
}

export function saveUIState(state) {
  try {
    localStorage.setItem(UI_STORE_KEY, JSON.stringify(state))
  } catch {}
}
