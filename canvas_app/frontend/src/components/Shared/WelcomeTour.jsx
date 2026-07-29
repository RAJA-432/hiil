import { useState } from 'react'

const STEPS = [
  {
    title: 'Welcome to hiil',
    description: 'Your AI-powered workspace for code, research, and writing. Let\'s take a quick tour.',
    icon: '✨',
  },
  {
    title: '💬 Chat with AI',
    description: 'Type any message in the composer below. The AI can read, write, and search your workspace files.',
    icon: '💬',
  },
  {
    title: '🧠 Switch Skills',
    description: 'Click the 🧠 tab in the sidebar to switch between specialized personas like Data Analyst or Code Reviewer.',
    icon: '🧠',
  },
  {
    title: '📁 Browse Files',
    description: 'Click the 📁 tab to browse your workspace. Click any file to preview it in the right panel.',
    icon: '📁',
  },
  {
    title: '🖼 Paste Images',
    description: 'Paste screenshots or drag images into the composer. The AI can analyze them.',
    icon: '🖼',
  },
  {
    title: '⌨️ Shortcuts',
    description: 'Press Ctrl+K to see all keyboard shortcuts. Ctrl+N for new conversation.',
    icon: '⌨️',
  },
]

export default function WelcomeTour({ onComplete }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]
  const last = step === STEPS.length - 1

  const handleNext = () => {
    if (last) {
      localStorage.setItem('hiil_tour_complete', 'true')
      onComplete?.()
    } else {
      setStep(step + 1)
    }
  }

  const handleSkip = () => {
    localStorage.setItem('hiil_tour_complete', 'true')
    onComplete?.()
  }

  return (
    <div className="welcome-overlay">
      <div className="welcome-card">
        <div className="welcome-icon">{current.icon}</div>
        <h2 className="welcome-title">{current.title}</h2>
        <p className="welcome-desc">{current.description}</p>
        <div className="welcome-dots">
          {STEPS.map((_, i) => (
            <span key={i} className={`welcome-dot ${i === step ? 'active' : ''}`} />
          ))}
        </div>
        <div className="welcome-actions">
          <button className="toolbar-btn" onClick={handleSkip}>Skip tour</button>
          <button className="settings-save-btn" onClick={handleNext}>
            {last ? 'Get started' : 'Next'}
          </button>
        </div>
        <div className="welcome-counter">{step + 1} of {STEPS.length}</div>
      </div>
    </div>
  )
}
