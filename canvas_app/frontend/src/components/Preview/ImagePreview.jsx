export default function ImagePreview({ filePath }) {
  if (filePath.startsWith('http')) {
    return <img src={filePath} alt={filePath} />
  }
  return (
    <div className="preview-empty">
      <p>Image preview not available in mock mode</p>
      <p style={{ fontSize: 11, color: 'var(--text-dim)' }}>{filePath}</p>
    </div>
  )
}
