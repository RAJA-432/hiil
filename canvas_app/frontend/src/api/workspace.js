const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

import { apiGet } from './client'
import { getMockFileTree, getMockFileContent } from './mock'

export async function getWorkspaceInfo() {
  if (USE_MOCK) return { name: 'hiil', root: '/home/user/hiil' }
  return apiGet('/api/workspace')
}

export { readFile as readWorkspaceFile, listDirectory as listWorkspaceDir } from './files'
