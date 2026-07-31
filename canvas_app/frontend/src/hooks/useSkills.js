import { useState, useEffect, useCallback } from 'react'
import { listSkills, activateSkill, getOutputSchema } from '../api/skills'

const ICON_MAP = {
  chart: '📊',
  code: '💻',
  pen: '✍️',
  layers: '🏗️',
  'search-lg': '🔬',
  sparkles: '✨',
}

export function getSkillIcon(skill) {
  return ICON_MAP[skill?.icon] || '🧠'
}

export function useSkills() {
  const [skills, setSkills] = useState([])
  const [activeSkill, setActiveSkill] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const all = await listSkills()
      setSkills(all)
      if (!activeSkill) {
        const general = all.find(s => s.id === 'general')
        if (general) setActiveSkill(general)
      }
    } catch {
      console.error('Failed to load skills')
    }
    setLoading(false)
  }, [activeSkill])

  useEffect(() => {
    refresh()
  }, [])

  const switchSkill = useCallback(async (skillId) => {
    try {
      const result = await activateSkill(skillId)
      if (result?.skill) {
        setActiveSkill(result.skill)
      } else {
        const found = skills.find(s => s.id === skillId)
        if (found) setActiveSkill(found)
      }
      getOutputSchema(skillId).then(schema => {
        if (schema) console.log(`[output-schema] ${skillId}:`, schema)
      }).catch(err => console.warn('Failed to fetch output schema:', err))
    } catch (err) {
      console.error('Failed to activate skill:', err)
      throw err
    }
  }, [skills])

  return { skills, activeSkill, switchSkill, loading, refresh }
}
