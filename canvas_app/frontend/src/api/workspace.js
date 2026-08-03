import { apiGet } from './client'
import { USE_MOCK } from './mocks'

export async function getWorkspaceInfo() {
  if (USE_MOCK) return { name: 'H.I.I.L.', root: '/home/user/hiil' }
  return apiGet('/api/workspace')
}


