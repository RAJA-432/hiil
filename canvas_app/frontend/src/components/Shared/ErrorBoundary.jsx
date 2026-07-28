import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          height: '100vh', padding: 32, textAlign: 'center', color: 'var(--text-dim)',
        }}>
          <h2 style={{ margin: '0 0 8px', color: 'var(--text)' }}>Something went wrong</h2>
          <p style={{ margin: '0 0 16px', fontSize: 13 }}>{this.state.error?.message}</p>
          <button
            onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
            style={{
              padding: '8px 16px', border: '1px solid var(--primary)', borderRadius: 'var(--radius-sm)',
              background: 'var(--primary-dim)', color: 'var(--primary)', cursor: 'pointer', fontSize: 13,
            }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}