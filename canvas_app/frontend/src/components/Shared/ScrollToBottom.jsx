import { useState, useEffect } from 'react'

export default function ScrollToBottom({ containerRef }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = containerRef?.current
    if (!el) return
    const handler = () => {
      const threshold = 200
      setVisible(el.scrollHeight - el.scrollTop - el.clientHeight > threshold)
    }
    el.addEventListener('scroll', handler)
    handler()
    return () => el.removeEventListener('scroll', handler)
  }, [containerRef])

  const handleClick = () => {
    const el = containerRef?.current
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }
  }

  if (!visible) return null

  return (
    <button className="scroll-to-bottom" onClick={handleClick} aria-label="Scroll to bottom">
      ↓
    </button>
  )
}
