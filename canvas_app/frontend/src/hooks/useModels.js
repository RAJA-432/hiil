import { useState, useEffect } from 'react'
import { listModels, setModel } from '../api/models'

export function useModels(initialModel) {
  const [models, setModels] = useState([])
  const [activeModel, setActiveModel] = useState(initialModel || 'gpt-4o-mini')

  useEffect(() => {
    listModels().then(setModels).catch(() => {})
  }, [])

  const switchModel = async (modelId) => {
    setActiveModel(modelId)
    try { await setModel(modelId) } catch {}
  }

  return { models, activeModel, switchModel }
}
