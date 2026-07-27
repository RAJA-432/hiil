import { useState } from 'react'

const toolLabels = {
  read_document: 'Reading file',
  edit_document: 'Editing file',
  write_file: 'Writing file',
  list_directory: 'Listing directory',
  search: 'Searching',
  web_search: 'Searching web',
}

export default function KaryaCall({ toolCall, onOpenFile }) {
  const [expanded, setExpanded] = useState(false)
  const { tool, status, args, result } = toolCall
  const label = toolLabels[tool] || `Running ${tool}`

  const isRunning = status === 'running'
  const icon = isRunning ? <span className="spinner" /> : '✓'

  const filePath = args?.path

  return (
    <div className="tool-call">
      <span className="tool-call-summary" onClick={() => setExpanded(!expanded)}>
        <span>{icon}</span>
        <span>{label}{filePath ? ` ${filePath}` : ''}...</span>
        <span style={{ fontSize: 10, marginLeft: 4 }}>{expanded ? '▲' : '▼'}</span>
      </span>
      {expanded && result && (
        <div className="tool-call-detail">{result}</div>
      )}
    </div>
  )
}
