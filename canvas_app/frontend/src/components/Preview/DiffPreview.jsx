import { useState, useMemo } from 'react'

function parseDiff(diffText) {
  const files = []
  let currentFile = null
  let currentLines = []

  for (const line of diffText.split('\n')) {
    if (line.startsWith('diff --git ')) {
      if (currentFile && currentLines.length > 0) {
        currentFile.lines = currentLines
        files.push(currentFile)
      }
      const path = line.replace('diff --git a/', '').replace(' b/', '')
      currentFile = { path, lines: [], additions: 0, deletions: 0 }
      currentLines = []
    } else if (line.startsWith('@@')) {
      currentLines.push({ text: line, type: 'meta' })
    } else if (currentFile) {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        currentLines.push({ text: line, type: 'add' })
        currentFile.additions++
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        currentLines.push({ text: line, type: 'del' })
        currentFile.deletions++
      } else {
        currentLines.push({ text: line, type: 'context' })
      }
    }
  }

  if (currentFile && currentLines.length > 0) {
    currentFile.lines = currentLines
    files.push(currentFile)
  }

  return files
}

export default function DiffPreview({ content }) {
  const [expandAll, setExpandAll] = useState(false)

  const files = useMemo(() => parseDiff(content || ''), [content])

  if (!content) {
    return <div className="preview-empty"><p>No diff content</p></div>
  }

  return (
    <div className="diff-preview">
      <div className="diff-header">
        <span className="diff-summary">
          {files.length} file{files.length !== 1 ? 's' : ''} changed
        </span>
        <button className="toolbar-btn" onClick={() => setExpandAll(!expandAll)}>
          {expandAll ? 'Collapse all' : 'Expand all'}
        </button>
      </div>
      {files.map((file, fi) => (
        <div key={fi} className="diff-file">
          <div className="diff-file-header">
            <span className="diff-file-path">{file.path}</span>
            <span className="diff-stats">
              <span className="diff-add">+{file.additions}</span>
              <span className="diff-del">-{file.deletions}</span>
            </span>
          </div>
          <div className={`diff-lines ${expandAll ? '' : 'diff-collapsed'}`}>
            {file.lines.map((line, li) => (
              <div key={li} className={`diff-line diff-line-${line.type}`}>
                <span className="diff-line-num">{li + 1}</span>
                <span className="diff-line-content">{line.text}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
