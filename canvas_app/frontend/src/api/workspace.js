import { apiGet } from './client'
import { USE_MOCK } from './mocks'

export async function getWorkspaceInfo() {
  if (USE_MOCK) return { name: 'hiil', root: '/home/user/hiil' }
  return apiGet('/api/workspace')
}


