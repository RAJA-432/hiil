import { useState, useMemo } from 'react'
import ConversationItem from './ConversationItem'
import Spinner from '../Shared/Spinner'

function groupByDate(conversations) {
  const now = new Date()
  const today = new Date(now)
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const lastWeek = new Date(today)
  lastWeek.setDate(lastWeek.getDate() - 7)

  const groups = { pinned: [], today: [], yesterday: [], thisWeek: [], earlier: [] }

  for (const c of conversations) {
    if (c.pinned) { groups.pinned.push(c); continue }
    const d = new Date(c.updated || c.created)
    if (d >= today) groups.today.push(c)
    else if (d >= yesterday) groups.yesterday.push(c)
    else if (d >= lastWeek) groups.thisWeek.push(c)
    else groups.earlier.push(c)
  }

  const labels = {
    pinned: 'Pinned',
    today: 'Today',
    yesterday: 'Yesterday',
    thisWeek: 'This Week',
    earlier: 'Earlier',
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([key, items]) => ({ label: labels[key], items }))
}

export default function ConversationList({ conversations, activeConversation, onSelect, onNew, onDelete, onRename, tags, onAddTag, onRemoveTag, onTogglePin, loading, hasMore, onLoadMore, loadingMore }) {
  const [tagFilter, setTagFilter] = useState(null)

  const allUsedTags = useMemo(() => {
    const set = new Set()
    Object.values(tags || {}).forEach(arr => arr.forEach(t => set.add(t)))
    return [...set].sort()
  }, [tags])

  const filtered = useMemo(() => {
    if (!tagFilter) return conversations
    return conversations.filter(c => (tags[c.id] || []).includes(tagFilter))
  }, [conversations, tagFilter, tags])

  const groups = groupByDate(filtered)

  return (
    <div className="conversation-list">
      <button className="conversation-new-btn" onClick={onNew} aria-label="New conversation">
        + New conversation
      </button>

      {allUsedTags.length > 0 && (
        <div className="conversation-tag-filters">
          {allUsedTags.map(tag => (
            <button
              key={tag}
              className={`tag-filter-btn ${tagFilter === tag ? 'active' : ''}`}
              onClick={() => setTagFilter(tagFilter === tag ? null : tag)}
            >
              {tag}
              {tagFilter === tag && ' ✕'}
            </button>
          ))}
          {tagFilter && (
            <button className="tag-filter-btn tag-filter-clear" onClick={() => setTagFilter(null)}>
              Clear all
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="conversations-loading" style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
          <Spinner size={20} label="Loading conversations..." />
        </div>
      ) : groups.map((group) => (
        <div key={group.label}>
          <div className="sidebar-section-header">
            {group.label}
            <span className="sidebar-section-count">{group.items.length}</span>
          </div>
          {group.items.map((conv) => (
            <ConversationItem
              key={conv.id}
              conversation={conv}
              active={activeConversation?.id === conv.id}
              onSelect={onSelect}
              onDelete={onDelete}
              onRename={onRename}
              tags={tags?.[conv.id] || []}
              onAddTag={onAddTag}
              onRemoveTag={onRemoveTag}
              pinned={conv.pinned}
              onTogglePin={onTogglePin}
            />
          ))}
        </div>
      ))}

      {!loading && hasMore && conversations.length > 0 && (
        <button
          className="conversation-new-btn conversation-load-more"
          onClick={onLoadMore}
          disabled={loadingMore}
          style={{ marginTop: 8 }}
        >
          {loadingMore ? <Spinner size={14} label="Loading more..." /> : 'Load more'}
        </button>
      )}

      {!loading && conversations.length === 0 && (
        <div className="conversation-empty">No conversations yet</div>
      )}
    </div>
  )
}
