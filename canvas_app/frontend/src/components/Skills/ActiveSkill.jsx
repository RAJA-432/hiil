import { getSkillIcon } from '../../hooks/useSkills'

export default function ActiveSkill({ skill, onClick }) {
  if (!skill || skill.id === 'general') return null

  return (
    <button className="active-skill toolbar-btn" onClick={onClick} title={`Active skill: ${skill.name}`}>
      <span className="active-skill-icon">{getSkillIcon(skill)}</span>
      <span className="active-skill-name">{skill.name}</span>
    </button>
  )
}
