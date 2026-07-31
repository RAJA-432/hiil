import { lazy, Suspense } from 'react'
import Spinner from '../Shared/Spinner'
import DiffPreview from './DiffPreview'

const MonacoPreview = lazy(() => import('./MonacoPreview'))
const MarkdownPreview = lazy(() => import('./MarkdownPreview'))
const ImagePreview = lazy(() => import('./ImagePreview'))

const LANGUAGES_MONACO = ['python', 'javascript', 'typescript', 'jsx', 'tsx', 'html', 'css', 'json', 'yaml', 'xml', 'sql', 'rust', 'go', 'java', 'cpp', 'c', 'shell', 'plaintext']
const LANGUAGES_MARKDOWN = ['markdown', 'md']
const LANGUAGES_IMAGE = ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']
const LANGUAGES_DIFF = ['diff']

function detectRenderer(language, filePath) {
  const ext = filePath?.split('.').pop()?.toLowerCase()
  if (LANGUAGES_DIFF.includes(language)) return 'diff'
  if (LANGUAGES_IMAGE.includes(ext)) return 'image'
  if (LANGUAGES_MARKDOWN.includes(language)) return 'markdown'
  if (LANGUAGES_MONACO.includes(language)) return 'monaco'
  return 'text'
}

export default function PreviewPanel({ filePath, content, language, loading, onClose, theme }) {
  if (!filePath) return null

  const fileName = filePath.split('/').pop() || filePath
  const renderer = detectRenderer(language, filePath)

  return (
    <div className="preview-panel" role="complementary" aria-label="File preview">
      <div className="preview-header">
        <div className="preview-header-title">
          <span>{fileName}</span>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{language}</span>
        </div>
        <button className="preview-header-close" onClick={onClose}>✕</button>
      </div>
      <div className="preview-body">
        <Suspense fallback={
          <div className="preview-empty">
            <Spinner size={20} />
            <p>Loading...</p>
          </div>
        }>
          {loading ? (
            <div className="preview-empty">
              <Spinner size={20} />
              <p>Loading...</p>
            </div>
          ) : renderer === 'monaco' ? (
            <MonacoPreview content={content} language={language} theme={theme} />
          ) : renderer === 'markdown' ? (
            <MarkdownPreview content={content} />
          ) : renderer === 'image' ? (
            <ImagePreview filePath={filePath} />
          ) : renderer === 'diff' ? (
            <DiffPreview content={content} />
          ) : (
            <pre style={{ padding: 16, fontFamily: 'var(--font-mono)', fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-all', overflow: 'auto', height: '100%' }}>{content}</pre>
          )}
        </Suspense>
      </div>
    </div>
  )
}
