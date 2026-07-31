import { useRef, useEffect, useCallback } from 'react'

export default function ResizablePanel({ side, defaultWidth = 260, minWidth = 160, maxWidth = 600, children, onWidthChange, gridArea }) {
  const widthRef = useRef(defaultWidth)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)
  const cssVar = side === 'left' ? '--sidebar-width' : '--preview-width'

  useEffect(() => {
    document.documentElement.style.setProperty(cssVar, `${defaultWidth}px`)
  }, [])

  const handleMouseDown = useCallback((e) => {
    dragging.current = true
    startX.current = e.clientX
    startW.current = widthRef.current
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  useEffect(() => {
    const onMove = (e) => {
      if (!dragging.current) return
      const delta = side === 'left' ? e.clientX - startX.current : startX.current - e.clientX
      const newWidth = Math.max(minWidth, Math.min(maxWidth, startW.current + delta))
      widthRef.current = newWidth
      document.documentElement.style.setProperty(cssVar, `${newWidth}px`)
    }
    const onUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      onWidthChange?.(widthRef.current)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [side, minWidth, maxWidth, cssVar, onWidthChange])

  return (
    <div style={{ position: 'relative', display: 'flex', minWidth: 0, gridArea }}>
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
