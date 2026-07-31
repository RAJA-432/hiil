import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Modal from './Modal'

describe('Modal', () => {
  it('renders children when open is true', () => {
    render(<Modal open onClose={vi.fn()} title="Test"><p>content</p></Modal>)
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('does not render when open is false', () => {
    render(<Modal open={false} onClose={vi.fn()}><p>content</p></Modal>)
    expect(screen.queryByText('content')).not.toBeInTheDocument()
  })

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose}>content</Modal>)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })

  it('calls onClose when overlay backdrop is clicked', () => {
    const onClose = vi.fn()
    render(<Modal open onClose={onClose}>content</Modal>)
    fireEvent.click(screen.getByRole('presentation'))
    expect(onClose).toHaveBeenCalled()
  })
})
