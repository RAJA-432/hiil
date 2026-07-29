import { useState, useEffect } from 'react'
import { listModels, setModel } from '../api/models'

export function useModels(initialModel) {
  const [models, setModels] = useState([])
  const [activeModel, setActiveModel] = useState(initialModel || 'gpt-4o-mini')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    listModels()
      .then(setModels)
      .catch((e) => console.warn('Failed to load models:', e))
      .finally(() => setLoading(false))
  }, [])

  const switchModel = async (modelId) => {
    setActiveModel(modelId)
    await setModel(modelId)
  }

  return { models, activeModel, switchModel, loading }
}
