const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet, apiPost } from './client'
import { getMockModels } from './mock'

export async function listModels() {
  if (USE_MOCK) return getMockModels()
  return (await apiGet('/api/models')).models || []
}

export async function setModel(modelId) {
  if (USE_MOCK) return modelId
  return apiPost('/api/model', { model: modelId })
}
