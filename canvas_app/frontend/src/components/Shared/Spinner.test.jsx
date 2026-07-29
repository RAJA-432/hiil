import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Spinner from './Spinner'

describe('Spinner', () => {
  it('renders without crashing', () => {
    render(<Spinner />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })
})
