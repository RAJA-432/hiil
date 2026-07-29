import { useState, useCallback } from 'react'

function TreeNode({ node, depth = 0, onOpenFile }) {
  const [expanded, setExpanded] = useState(depth < 1)
  const isDir = node.type === 'dir'

  const handleClick = () => {
    if (isDir) {
      setExpanded(!expanded)
    } else {
      onOpenFile(node.path || node.name)
    }
  }

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleClick()
    }
  }, [isDir, expanded, node, onOpenFile])

  const icon = isDir ? (expanded ? '▼' : '▶') : '○'

  return (
    <div>
      <div
        className="file-tree-item"
        style={{ paddingLeft: 8 + depth * 16 }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="treeitem"
        tabIndex={0}
        aria-expanded={isDir ? expanded : undefined}
        aria-label={node.name}
      >
        <span className="icon" aria-hidden="true">{icon}</span>
        <span className="truncate">{node.name}</span>
      </div>
      {isDir && expanded && node.children && (
        <div className="file-tree-children" role="group">
          {node.children.map((child) => (
            <TreeNode key={child.path || child.name} node={child} depth={depth + 1} onOpenFile={onOpenFile} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FileTree({ tree, onOpenFile, error }) {
  if (error) {
    return (
      <div className="file-tree" role="tree" aria-label="Workspace files">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--error-color, #e74c3c)', fontSize: 13 }}>
          <span role="img" aria-label="error">⚠️</span> {error}
        </div>
      </div>
    )
  }

  if (!tree) {
    return (
      <div className="file-tree" role="tree" aria-label="Workspace files">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
          Loading...
        </div>
      </div>
    )
  }

  return (
    <div className="file-tree" role="tree" aria-label="Workspace files">
      <TreeNode node={tree} depth={0} onOpenFile={onOpenFile} />
    </div>
  )
}
