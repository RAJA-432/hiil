import { getSkillIcon } from '../../hooks/useSkills'

export default function SkillCard({ skill, active, onSelect, onShowDetail }) {
  const icon = getSkillIcon(skill)

  return (
    <button
      className={`skill-card ${active ? 'skill-card-active' : ''}`}
      onClick={() => onSelect(skill.id)}
      type="button"
      aria-pressed={active}
      aria-label={`${skill.name}: ${skill.description}`}
    >
      <span className="skill-card-icon" style={{ background: skill.color + '20', color: skill.color }} aria-hidden="true">
        {icon}
      </span>
      <span className="skill-card-body">
        <span className="skill-card-name">{skill.name}</span>
        <span className="skill-card-desc">{skill.description}</span>
      </span>
      <span className="skill-card-meta">
        <span className="skill-card-templates">{skill.promptTemplates?.length || 0} prompts</span>
        <span className="skill-card-tools">{skill.toolPresets?.length || 0} tools</span>
      </span>
      {active && <span className="skill-card-active-badge" aria-label="Active skill">Active</span>}
    </button>
  )
}
