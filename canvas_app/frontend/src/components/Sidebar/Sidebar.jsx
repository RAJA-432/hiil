import { useState, useRef, lazy, Suspense } from 'react'
import { useUIContext } from '../../context/UIContext'
import { useChatContext } from '../../context/ChatContext'
import ConversationList from './ConversationList'
import FileTree from './FileTree'
import SearchPanel from '../Shared/SearchPanel'
const SkillsPanel = lazy(() => import('../Skills/SkillsPanel'))

export default function Sidebar() {
  const { sidebarOpen, setSidebarOpen, sidebarView, setSidebarView, fileTree, fileTreeError, skills, activeSkill, skillsLoading, openFile, handleSelectSkill } = useUIContext()
  const { conversations, activeConversation, conversationsLoading, tags, addTag, removeTag, handleSelectConversation, handleNewConversation, handleDeleteConversation, handleRenameConversation, handleTogglePin, loadMoreConversations, hasMore, loadingMore } = useChatContext()
  const [searchValue, setSearchValue] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const inputRef = useRef(null)

  const handleSearchOpen = () => {
    setSearchOpen(true)
    setSidebarView('search')
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const handleSearchClose = () => {
    setSearchOpen(false)
    setSearchValue('')
    setSidebarView('conversations')
  }

  return (
    <>
      <div className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`} onClick={() => setSidebarOpen(false)} />
      <div className={`sidebar ${sidebarOpen ? 'mobile-open' : ''}`} role="navigation" aria-label="Sidebar">
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
            className={`toolbar-btn ${sidebarView === 'conversations' ? 'active' : ''}`}
            onClick={() => { setSearchOpen(false); setSidebarView('conversations') }}
            title="Conversations"
            role="tab"
            aria-selected={sidebarView === 'conversations'}
            aria-controls="panel-conversations"
            aria-label="Conversations"
          >
            💬
          </button>
          <button
            className={`toolbar-btn ${sidebarView === 'skills' ? 'active' : ''}`}
            onClick={() => { setSearchOpen(false); setSidebarView('skills') }}
            title="Skills"
            role="tab"
            aria-selected={sidebarView === 'skills'}
            aria-controls="panel-skills"
            aria-label="Skills"
          >
            🧠
          </button>
          <button
            className={`toolbar-btn ${sidebarView === 'files' ? 'active' : ''}`}
            onClick={() => { setSearchOpen(false); setSidebarView('files') }}
            title="Files"
            role="tab"
            aria-selected={sidebarView === 'files'}
            aria-controls="panel-files"
            aria-label="Files"
          >
            📁
          </button>
        </div>

        {sidebarView === 'search' && searchOpen ? (
          <div id="panel-conversations" role="tabpanel" aria-labelledby="tab-conversations">
            <SearchPanel
              conversations={conversations}
              onSelectConversation={(conv) => { handleSelectConversation(conv); handleSearchClose() }}
              onClose={handleSearchClose}
            />
          </div>
        ) : sidebarView === 'skills' ? (
          <div id="panel-skills" role="tabpanel" aria-labelledby="tab-skills">
            <Suspense fallback={<div className="sidebar-loading" style={{padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)'}}>Loading skills…</div>}>
              <SkillsPanel
                skills={skills}
                activeSkill={activeSkill}
                onSelectSkill={handleSelectSkill}
                loading={skillsLoading}
              />
            </Suspense>
          </div>
        ) : sidebarView === 'files' ? (
          <div id="panel-files" role="tabpanel" aria-labelledby="tab-files">
            <FileTree tree={fileTree} onOpenFile={openFile} error={fileTreeError} />
          </div>
        ) : (
          <div id="panel-conversations" role="tabpanel" aria-labelledby="tab-conversations">
            <ConversationList
              conversations={conversations}
              activeConversation={activeConversation}
              onSelect={handleSelectConversation}
              onNew={handleNewConversation}
              onDelete={handleDeleteConversation}
              onRename={handleRenameConversation}
              loading={conversationsLoading}
              hasMore={hasMore}
              onLoadMore={loadMoreConversations}
              loadingMore={loadingMore}
              tags={tags}
              onAddTag={addTag}
              onRemoveTag={removeTag}
              onTogglePin={handleTogglePin}
            />
          </div>
        )}
      </div>
    </>
  )
}
