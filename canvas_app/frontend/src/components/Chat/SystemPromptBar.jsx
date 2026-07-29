import { useState } from 'react'
import { getSkillIcon } from '../../hooks/useSkills'

export default function SystemPromptBar({ activeSkill }) {
  const [expanded, setExpanded] = useState(false)

  if (!activeSkill || activeSkill.id === 'general') return null

  const icon = getSkillIcon(activeSkill)
  const prompt = activeSkill.systemPrompt || ''
  const preview = prompt.slice(0, 80)

  return (
    <div className="system-prompt-bar" onClick={() => setExpanded(!expanded)} role="button" tabIndex={0} aria-expanded={expanded} aria-label={`Active skill: ${activeSkill.name}`} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpanded(!expanded) } }}>
      <div className="system-prompt-header">
        <span className="system-prompt-icon" aria-hidden="true">{icon}</span>
        <span className="system-prompt-name">{activeSkill.name}</span>
        <span className="system-prompt-tools">{activeSkill.toolPresets?.length || 0} tools</span>
        <span className="system-prompt-arrow">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="system-prompt-content">
          <div className="system-prompt-label">System Prompt</div>
          <div className="system-prompt-text">{prompt}</div>
          <div className="system-prompt-label">Allowed Tools</div>
          <div className="system-prompt-tool-list">
            {activeSkill.toolPresets?.map(t => (
              <span key={t} className="system-prompt-tool-tag">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
