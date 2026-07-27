import ConversationList from './ConversationList'
import FileTree from './FileTree'

export default function Sidebar({ view, onViewChange, conversations, activeConversation, onSelectConversation, onNewConversation, onDeleteConversation, fileTree, onOpenFile }) {
  return (
    <div className="sidebar">
      <div className="sidebar-search">
        <input
          type="text"
          placeholder="Search..."
          onFocus={() => onViewChange('search')}
        />
      </div>

      <div style={{ display: 'flex', gap: 4, padding: '4px 12px', borderBottom: '1px solid var(--border)' }}>
        <button
          className={`toolbar-btn ${view === 'conversations' ? 'active' : ''}`}
          onClick={() => onViewChange('conversations')}
          style={{ flex: 1, fontSize: 11 }}
        >
          Chats
        </button>
        <button
          className={`toolbar-btn ${view === 'files' ? 'active' : ''}`}
          onClick={() => onViewChange('files')}
          style={{ flex: 1, fontSize: 11 }}
        >
          Files
        </button>
      </div>

      {view === 'conversations' ? (
        <ConversationList
          conversations={conversations}
          activeConversation={activeConversation}
          onSelect={onSelectConversation}
          onNew={onNewConversation}
          onDelete={onDeleteConversation}
        />
      ) : (
        <FileTree
          tree={fileTree}
          onOpenFile={onOpenFile}
        />
      )}
    </div>
  )
}
