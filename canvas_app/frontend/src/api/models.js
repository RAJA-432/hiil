import { apiGet, apiPost } from './client'
import { USE_MOCK, getMockModels } from './mocks'

export async function listModels() {
  if (USE_MOCK) return getMockModels()
  return (await apiGet('/api/models')).models || []
}

export async function setModel(modelId) {
  if (USE_MOCK) return modelId
  return apiPost('/api/model', { model: modelId })
}
