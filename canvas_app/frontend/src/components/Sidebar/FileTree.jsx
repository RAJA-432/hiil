import { useState } from 'react'

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

  const icon = isDir ? (expanded ? '▼' : '▶') : '○'

  return (
    <div>
      <div
        className="file-tree-item"
        style={{ paddingLeft: 8 + depth * 16 }}
        onClick={handleClick}
      >
        <span className="icon">{icon}</span>
        <span className="truncate">{node.name}</span>
      </div>
      {isDir && expanded && node.children && (
        <div className="file-tree-children">
          {node.children.map((child, i) => (
            <TreeNode key={`${child.name}-${i}`} node={child} depth={depth + 1} onOpenFile={onOpenFile} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function FileTree({ tree, onOpenFile }) {
  if (!tree) {
    return (
      <div className="file-tree">
        <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
          Loading...
        </div>
      </div>
    )
  }

  return (
    <div className="file-tree">
      <TreeNode node={tree} depth={0} onOpenFile={onOpenFile} />
    </div>
  )
}
