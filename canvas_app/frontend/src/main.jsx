import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import ErrorBoundary from './components/Shared/ErrorBoundary'
import './styles/index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)

const splash = document.getElementById('splash')
if (splash) splash.remove()

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {})
}

document.documentElement.lang = localStorage.getItem('lang') || 'en'

window.removeEventListener('error', window.__HTML_ERROR_FALLBACK)
window.removeEventListener('unhandledrejection', window.__HTML_ERROR_FALLBACK)
