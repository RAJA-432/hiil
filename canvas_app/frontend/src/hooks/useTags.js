import { useState, useCallback } from 'react'

const STORAGE_KEY = 'hiil_tags'

function loadTags() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveTags(tags) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(tags)) } catch { /* best-effort persistence */ }
}

export function useTags() {
  const [tags, setTags] = useState(loadTags)

  const getTagsFor = useCallback((conversationId) => {
    return tags[conversationId] || []
  }, [tags])

  const addTag = useCallback((conversationId, tag) => {
    const t = tag.trim().toLowerCase()
    if (!t) return
    setTags(prev => {
      const next = { ...prev }
      const existing = next[conversationId] || []
      if (existing.includes(t)) return prev
      next[conversationId] = [...existing, t]
      saveTags(next)
      return next
    })
  }, [])

  const removeTag = useCallback((conversationId, tag) => {
    setTags(prev => {
      const next = { ...prev }
      next[conversationId] = (next[conversationId] || []).filter(t => t !== tag)
      if (next[conversationId].length === 0) delete next[conversationId]
      saveTags(next)
      return next
    })
  }, [])

  const allTags = useCallback(() => {
    const set = new Set()
    Object.values(tags).forEach(arr => arr.forEach(t => set.add(t)))
    return [...set].sort()
  }, [tags])

  return { tags, getTagsFor, addTag, removeTag, allTags: allTags() }
}
