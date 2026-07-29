export function MessageSkeleton({ count = 3 }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`skeleton-message ${i % 2 === 0 ? 'skeleton-user' : 'skeleton-assistant'}`}>
          <div className="skeleton-line skeleton-line-short" />
          <div className="skeleton-line skeleton-line-medium" />
          {i % 2 === 1 && <div className="skeleton-line skeleton-line-long" />}
        </div>
      ))}
    </div>
  )
}

export function FileTreeSkeleton() {
  return (
    <div className="skeleton-list" style={{ padding: '8px 12px' }}>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="skeleton-row" style={{ paddingLeft: i > 2 ? 20 : 0 }}>
          <div className="skeleton-line skeleton-line-file" />
        </div>
      ))}
    </div>
  )
}

export function SkillsSkeleton() {
  return (
    <div className="skeleton-list" style={{ padding: '12px' }}>
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="skeleton-card" style={{ marginBottom: 10, borderRadius: 8 }}>
          <div className="skeleton-line skeleton-line-short" />
          <div className="skeleton-line skeleton-line-medium" style={{ marginTop: 6 }} />
        </div>
      ))}
    </div>
  )
}
