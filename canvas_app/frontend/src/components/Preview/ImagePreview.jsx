import { useState, useEffect } from 'react'

export default function ImagePreview({ filePath }) {
  const [src, setSrc] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!filePath) return
    if (filePath.startsWith('http')) {
      setSrc(filePath)
      return
    }
    setSrc(null)
    setError(null)
    fetch(`/api/files/${encodeURIComponent(filePath)}`)
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.blob()
      })
      .then(blob => {
        setSrc(URL.createObjectURL(blob))
      })
      .catch(err => {
        setError(err.message)
      })
    return () => {
      if (src && src.startsWith('blob:')) URL.revokeObjectURL(src)
    }
  }, [filePath])

  if (src) {
    return <img src={src} alt={filePath} style={{ maxWidth: '100%' }} />
  }
  return (
    <div className="preview-empty">
      <p>{error ? `Error: ${error}` : 'Loading...'}</p>
      <p style={{ fontSize: 11, color: 'var(--text-dim)' }}>{filePath}</p>
    </div>
  )
}
