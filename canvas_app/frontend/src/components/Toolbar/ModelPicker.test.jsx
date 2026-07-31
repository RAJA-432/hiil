import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ModelPicker from './ModelPicker'

const models = [
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
  { id: 'gpt-4o', name: 'GPT-4o' },
]

describe('ModelPicker', () => {
  it('renders without crashing', () => {
    render(<ModelPicker models={[]} />)
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('shows "Loading models..." when loading is true', () => {
    render(<ModelPicker models={[]} loading />)
    expect(screen.getByText('Loading models...')).toBeInTheDocument()
  })

  it('shows model options when models are provided', () => {
    render(<ModelPicker models={models} />)
    expect(screen.getByText('GPT-4o Mini')).toBeInTheDocument()
    expect(screen.getByText('GPT-4o')).toBeInTheDocument()
  })

  it('calls onChange when selection changes', () => {
    const onSwitch = vi.fn()
    render(<ModelPicker models={models} onSwitch={onSwitch} />)
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'gpt-4o' } })
    expect(onSwitch).toHaveBeenCalledWith('gpt-4o')
  })
})
