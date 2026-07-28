const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet } from './client'
import { getMockFileTree, getMockFileContent } from './mock'

export async function readFile(path) {
  if (USE_MOCK) return { path, content: getMockFileContent(path), language: detectLanguage(path), size: getMockFileContent(path).length }
  const res = await fetch(`/api/files/${encodeURIComponent(path)}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const ct = res.headers.get('Content-Type') || ''
  let content
  if (ct.startsWith('text/') || ct.includes('json') || ct.includes('javascript')) {
    content = await res.text()
  } else {
    content = await res.text()
  }
  return { path, content, language: detectLanguage(path), size: parseInt(res.headers.get('X-File-Size') || '0', 10) }
}

export async function listDirectory(dir) {
  if (USE_MOCK) return getMockFileTree()
  return apiGet(`/api/list?dir=${encodeURIComponent(dir)}`)
}

export async function getFileTree() {
  if (USE_MOCK) return getMockFileTree()
  return apiGet('/api/list?dir=.&recursive=true')
}

function detectLanguage(path) {
  const ext = path.split('.').pop()?.toLowerCase()
  const map = {
    py: 'python', js: 'javascript', jsx: 'javascript', ts: 'typescript',
    tsx: 'typescript', html: 'html', css: 'css', json: 'json',
    md: 'markdown', yaml: 'yaml', yml: 'yaml', toml: 'ini',
    sql: 'sql', sh: 'shell', bash: 'shell', rs: 'rust',
    go: 'go', java: 'java', c: 'c', cpp: 'cpp', h: 'c',
    txt: 'text', env: 'dotenv', cfg: 'ini', conf: 'ini',
    xml: 'xml', svg: 'xml', dockerfile: 'dockerfile',
  }
  return map[ext] || 'plaintext'
}
