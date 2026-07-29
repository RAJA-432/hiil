import { useState, useMemo } from 'react'
import SkillCard from './SkillCard'
import { getSkillIcon } from '../../hooks/useSkills'

const CATEGORIES = [
  { id: 'all', label: 'All Skills' },
  { id: 'general', label: 'General' },
  { id: 'development', label: 'Development' },
  { id: 'analysis', label: 'Data & Analysis' },
  { id: 'writing', label: 'Writing' },
]

export default function SkillsPanel({ skills, activeSkill, onSelectSkill }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    let list = skills
    if (filter !== 'all') {
      list = list.filter(s => s.category === filter)
    }
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(s =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q)
      )
    }
    return list
  }, [skills, filter, query])

  return (
    <div className="skills-panel">
      <div className="skills-panel-header">
        <h3 className="skills-panel-title">Skills</h3>
        <span className="skills-panel-count">{skills.length} available</span>
      </div>

      <div className="skills-panel-search">
        <input
          type="text"
          className="skills-search-input"
          placeholder="Search skills..."
          aria-label="Search skills"
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
      </div>

      <div className="skills-panel-categories" role="tablist" aria-label="Skill categories">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            className={`skills-cat-btn ${filter === cat.id ? 'active' : ''}`}
            onClick={() => setFilter(cat.id)}
            role="tab"
            aria-selected={filter === cat.id}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="skills-panel-list">
        {filtered.map(skill => (
          <SkillCard
            key={skill.id}
            skill={skill}
            active={activeSkill?.id === skill.id}
            onSelect={onSelectSkill}
          />
        ))}
        {filtered.length === 0 && (
          <div className="skills-empty">No skills match your filter.</div>
        )}
      </div>

      {activeSkill && activeSkill.id !== 'general' && (
        <div className="skills-active-bar">
          <div className="skills-active-info">
            <span>{getSkillIcon(activeSkill)}</span>
            <span className="skills-active-name">{activeSkill.name}</span>
          </div>
          <button
            className="toolbar-btn"
            onClick={() => onSelectSkill('general')}
            aria-label="Reset to general skill"
          >
            Reset
          </button>
        </div>
      )}
    </div>
  )
}
