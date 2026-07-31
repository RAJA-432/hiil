import { useState, useRef, lazy, Suspense } from 'react'
import { useUIContext } from '../../context/UIContext'
import { useChatContext } from '../../context/ChatContext'
import ConversationList from './ConversationList'
import SearchPanel from '../Shared/SearchPanel'
const SkillsPanel = lazy(() => import('../Skills/SkillsPanel'))
const AgentPanel = lazy(() => import('../Agents/AgentPanel'))

export default function Sidebar() {
  const { sidebarOpen, setSidebarOpen, sidebarView, setSidebarView, skills, activeSkill, skillsLoading, handleSelectSkill, agents, agentsLoading, agentRunning, createAgent, runAgent, stopAgent, setAgentCreateOpen, setAgentToRun } = useUIContext()
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
      <nav className={`sidebar ${sidebarOpen ? 'mobile-open' : ''}`} aria-label="Sidebar">
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
            id="tab-conversations"
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
            id="tab-skills"
          >
            🧠
          </button>
          <button
            className={`toolbar-btn ${sidebarView === 'agents' ? 'active' : ''}`}
            onClick={() => { setSearchOpen(false); setSidebarView('agents') }}
            title="Agents"
            role="tab"
            aria-selected={sidebarView === 'agents'}
            aria-controls="panel-agents"
            aria-label="Agents"
            id="tab-agents"
          >
            🤖
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
        ) : sidebarView === 'agents' ? (
          <div id="panel-agents" role="tabpanel" aria-labelledby="tab-agents">
            <Suspense fallback={<div className="sidebar-loading" style={{padding: '1rem', textAlign: 'center', color: 'var(--text-secondary)'}}>Loading agents…</div>}>
              <AgentPanel
                agents={agents}
                loading={agentsLoading}
                onRun={(agent) => setAgentToRun(agent)}
                onStop={stopAgent}
                onCreate={() => setAgentCreateOpen(true)}
              />
            </Suspense>
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
      </nav>
    </>
  )
}
