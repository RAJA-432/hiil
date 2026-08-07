import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ToolActivityPanel from './ToolActivityPanel'

const PHASES = [
  { agent_id: 'session-123', phase: 'THINKING', timestamp: '2025-01-01T00:00:00Z', iteration: 1 },
  { agent_id: 'session-123', phase: 'EXECUTING', timestamp: '2025-01-01T00:00:01Z', iteration: 1 },
  { agent_id: 'session-123', phase: 'DONE', timestamp: '2025-01-01T00:00:02Z', iteration: 1 },
  { agent_id: 'sub-456', phase: 'DELEGATING', timestamp: '2025-01-01T00:00:03Z', iteration: null },
]

describe('ToolActivityPanel', () => {
  it('renders phase chips grouped by agent id', () => {
    render(<ToolActivityPanel logs={[]} ragChunks={[]} phases={PHASES} />)

    expect(screen.getByText('session-123')).toBeInTheDocument()
    expect(screen.getByText('sub-456')).toBeInTheDocument()

    expect(screen.getByText('THINKING')).toBeInTheDocument()
    expect(screen.getByText('EXECUTING')).toBeInTheDocument()
    expect(screen.getByText('DONE')).toBeInTheDocument()
    expect(screen.getByText('DELEGATING')).toBeInTheDocument()
  })

  it('applies a per-phase class to each chip', () => {
    const { container } = render(<ToolActivityPanel logs={[]} ragChunks={[]} phases={PHASES} />)

    expect(container.querySelector('.activity-phase-chip.thinking')).toBeInTheDocument()
    expect(container.querySelector('.activity-phase-chip.executing')).toBeInTheDocument()
    expect(container.querySelector('.activity-phase-chip.done')).toBeInTheDocument()
    expect(container.querySelector('.activity-phase-chip.delegating')).toBeInTheDocument()
  })

  it('renders nothing when phases, logs and rag chunks are empty', () => {
    const { container } = render(<ToolActivityPanel logs={[]} ragChunks={[]} phases={[]} />)

    expect(container.querySelector('.activity-panel')).toBeNull()
  })
})
