import { useState, useRef } from 'react'
import ConversationList from './ConversationList'
import FileTree from './FileTree'
import SearchPanel from '../Shared/SearchPanel'
import SkillsPanel from '../Skills/SkillsPanel'

export default function Sidebar({ view, onViewChange, conversations, activeConversation, onSelectConversation, onNewConversation, onDeleteConversation, onRenameConversation, fileTree, onOpenFile, skills, activeSkill, onSelectSkill, tags, onAddTag, onRemoveTag, onSearchResults }) {
  const [searchValue, setSearchValue] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const inputRef = useRef(null)

  const handleSearchOpen = () => {
    setSearchOpen(true)
    onViewChange('search')
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleSearchClose = () => {
    setSearchOpen(false)
    setSearchValue('')
    onViewChange('conversations')
  }

  return (
    <div className="sidebar" role="navigation" aria-label="Sidebar">
      <div className="sidebar-search">
        <input
          ref={inputRef}
          type="text"
          placeholder="Search conversations..."
          aria-label="Search conversations"
          value={searchOpen ? searchValue : ''}
          onChange={e => setSearchValue(e.target.value)}
          onFocus={handleSearchOpen}
          readOnly={!searchOpen}
        />
      </div>

      <div className="sidebar-tabs" role="tablist" aria-label="View tabs">
        <button
          className={`toolbar-btn ${view === 'conversations' ? 'active' : ''}`}
          onClick={() => { setSearchOpen(false); onViewChange('conversations') }}
          title="Conversations"
          role="tab"
          aria-selected={view === 'conversations'}
          aria-label="Conversations"
        >
          💬
        </button>
        <button
          className={`toolbar-btn ${view === 'skills' ? 'active' : ''}`}
          onClick={() => { setSearchOpen(false); onViewChange('skills') }}
          title="Skills"
          role="tab"
          aria-selected={view === 'skills'}
          aria-label="Skills"
        >
          🧠
        </button>
        <button
          className={`toolbar-btn ${view === 'files' ? 'active' : ''}`}
          onClick={() => { setSearchOpen(false); onViewChange('files') }}
          title="Files"
          role="tab"
          aria-selected={view === 'files'}
          aria-label="Files"
        >
          📁
        </button>
      </div>

      {view === 'search' && searchOpen ? (
        <SearchPanel
          conversations={conversations}
          onSelectConversation={(conv) => { onSelectConversation(conv); handleSearchClose() }}
          onClose={handleSearchClose}
          onResults={onSearchResults}
        />
      ) : view === 'skills' ? (
        <SkillsPanel
          skills={skills}
          activeSkill={activeSkill}
          onSelectSkill={onSelectSkill}
        />
      ) : view === 'files' ? (
        <FileTree tree={fileTree} onOpenFile={onOpenFile} />
      ) : (
        <ConversationList
          conversations={conversations}
          activeConversation={activeConversation}
          onSelect={onSelectConversation}
          onNew={onNewConversation}
          onDelete={onDeleteConversation}
          onRename={onRenameConversation}
        />
      )}
    </div>
  )
}
