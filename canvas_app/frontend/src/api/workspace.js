const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet } from './client'
import { getMockFileTree, getMockFileContent } from './mock'

export async function getWorkspaceInfo() {
  if (USE_MOCK) return { name: 'hiil', root: '/home/user/hiil' }
  return apiGet('/api/workspace')
}


