import { getSkillIcon } from '../../hooks/useSkills'

export default function SkillCard({ skill, active, onSelect, onShowDetail }) {
  const icon = getSkillIcon(skill)

  return (
    <div
      className={`skill-card ${active ? 'skill-card-active' : ''}`}
      onClick={() => onSelect(skill.id)}
      role="button"
      tabIndex={0}
      aria-selected={active}
      aria-label={`${skill.name}: ${skill.description}`}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(skill.id) } }}
    >
      <div className="skill-card-icon" style={{ background: skill.color + '20', color: skill.color }} aria-hidden="true">
        {icon}
      </div>
      <div className="skill-card-body">
        <div className="skill-card-name">{skill.name}</div>
        <div className="skill-card-desc">{skill.description}</div>
      </div>
      <div className="skill-card-meta">
        <span className="skill-card-templates">{skill.promptTemplates?.length || 0} prompts</span>
        <span className="skill-card-tools">{skill.toolPresets?.length || 0} tools</span>
      </div>
      {active && <div className="skill-card-active-badge" aria-label="Active skill">Active</div>}
    </div>
  )
}
