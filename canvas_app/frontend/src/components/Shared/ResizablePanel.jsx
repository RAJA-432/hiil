import { useState, useCallback, useRef, useEffect } from 'react'

export default function ResizablePanel({ side, defaultWidth = 260, minWidth = 160, maxWidth = 600, children, onWidthChange }) {
  const [width, setWidth] = useState(defaultWidth)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const handleMouseDown = useCallback((e) => {
    dragging.current = true
    startX.current = e.clientX
    startW.current = width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [width])

  const handleMouseMove = useCallback((e) => {
    if (!dragging.current) return
    const delta = side === 'left' ? e.clientX - startX.current : startX.current - e.clientX
    const newWidth = Math.max(minWidth, Math.min(maxWidth, startW.current + delta))
    setWidth(newWidth)
  }, [side, minWidth, maxWidth])

  const handleMouseUp = useCallback(() => {
    if (!dragging.current) return
    dragging.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    onWidthChange?.(width)
  }, [onWidthChange, width])

  useEffect(() => {
    if (!dragging.current) return
    const onMove = (e) => handleMouseMove(e)
    const onUp = () => handleMouseUp()
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [handleMouseMove, handleMouseUp])

  return (
    <div style={{ width, position: 'relative', display: 'flex', minWidth: 0 }}>
      {children}
      <div
        className="resize-handle"
        onMouseDown={handleMouseDown}
        style={{
          position: 'absolute',
          top: 0,
          [side === 'left' ? 'right' : 'left']: -3,
          width: 6,
          height: '100%',
          cursor: 'col-resize',
          zIndex: 20,
        }}
      />
    </div>
  )
}
