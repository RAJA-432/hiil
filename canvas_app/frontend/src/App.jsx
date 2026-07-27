import { useState, useEffect, useCallback } from 'react'
import { useChat } from './hooks/useChat'
import { useWorkspace } from './hooks/useWorkspace'
import { useModels } from './hooks/useModels'
import { useSettings } from './hooks/useSettings'
import { loadConversations, createConversation, deleteConversation } from './api/chat'
import Toolbar from './components/Toolbar/Toolbar'
import Sidebar from './components/Sidebar/Sidebar'
import ChatPanel from './components/Chat/ChatPanel'
import PreviewPanel from './components/Preview/PreviewPanel'
import Composer from './components/Composer/Composer'

export default function App() {
  const { settings, update: updateSettings } = useSettings()
  const { models, activeModel, switchModel } = useModels(settings.model)
  const { fileTree, selectedFile, fileContent, fileLanguage, loading: fileLoading, loadFileTree, openFile, closeFile } = useWorkspace()
  const [activeConversation, setActiveConversation] = useState(null)
  const [conversations, setConversations] = useState([])
  const [sidebarView, setSidebarView] = useState('conversations')

  const { messages, streaming, streamingText, send, stop, loadMessages } = useChat(activeConversation?.id)

  useEffect(() => {
    loadConversations()
      .then(setConversations)
      .catch(err => console.error('Failed to load conversations:', err))
    loadFileTree().catch(err => console.error('Failed to load file tree:', err))
  }, [])

  useEffect(() => {
    if (activeConversation) {
      loadMessages().catch(err => console.error('Failed to load messages:', err))
    }
  }, [activeConversation?.id, loadMessages])

  useEffect(() => {
    if (activeConversation) loadMessages()
  }, [activeConversation?.id])

  useEffect(() => {
    document.documentElement.className = settings.theme === 'light' ? 'light' : ''
  }, [settings.theme])

  const style = {
    '--sidebar-width': `${settings.sidebarWidth}px`,
    '--preview-width': selectedFile ? `${settings.previewWidth}px` : '0px',
  }

  const handleNewConversation = useCallback(async () => {
    const id = await createConversation()
    const conv = { id, title: `Conversation ${conversations.length + 1}`, created: new Date().toISOString(), updated: new Date().toISOString(), message_count: 0 }
    setConversations(prev => [conv, ...prev])
    setActiveConversation(conv)
  }, [conversations.length])

  const handleSelectConversation = useCallback((conv) => {
    setActiveConversation(conv)
  }, [])

  const handleDeleteConversation = useCallback(async (id) => {
    await deleteConversation(id)
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConversation?.id === id) setActiveConversation(null)
  }, [activeConversation])

  const handleSend = useCallback((text) => {
    if (streaming) return
    send(text)
  }, [send, streaming])

  const handleStop = useCallback(() => {
    stop()
  }, [stop])

  const handleOpenFile = useCallback((path) => {
    openFile(path)
  }, [openFile])

  const handleClosePreview = useCallback(() => {
    closeFile()
  }, [closeFile])

  const layoutClass = [
    'canvas-layout',
    !selectedFile && 'preview-hidden',
    !settings.sidebarVisible && 'sidebar-hidden',
  ].filter(Boolean).join(' ')

  return (
    <div className={layoutClass} style={style}>
      <Toolbar
        brand="hiil"
        activeModel={activeModel}
        models={models}
        onSwitchModel={switchModel}
        sidebarVisible={settings.sidebarVisible}
        previewVisible={!!selectedFile}
        onToggleSidebar={() => updateSettings({ sidebarVisible: !settings.sidebarVisible })}
        settings={settings}
        onUpdateSettings={updateSettings}
      />
      <Sidebar
        view={sidebarView}
        onViewChange={setSidebarView}
        conversations={conversations}
        activeConversation={activeConversation}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        fileTree={fileTree}
        onOpenFile={handleOpenFile}
      />
      <ChatPanel
        messages={messages}
        streaming={streaming}
        streamingText={streamingText}
        activeConversation={activeConversation}
        onOpenFile={handleOpenFile}
      />
      <PreviewPanel
        filePath={selectedFile}
        content={fileContent}
        language={fileLanguage}
        loading={fileLoading}
        onClose={handleClosePreview}
        theme={settings.theme}
      />
      <Composer
        streaming={streaming}
        onSend={handleSend}
        onStop={handleStop}
      />
    </div>
  )
}
