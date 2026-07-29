import { useState, useEffect, useCallback } from 'react'
import { useChat } from './hooks/useChat'
import { useWorkspace } from './hooks/useWorkspace'
import { useModels } from './hooks/useModels'
import { useSettings } from './hooks/useSettings'
import { useToast } from './hooks/useToast'
import { useSkills } from './hooks/useSkills'
import { useTags } from './hooks/useTags'
import { loadConversations, createConversation, deleteConversation, renameConversation } from './api/chat'
import Toolbar from './components/Toolbar/Toolbar'
import Sidebar from './components/Sidebar/Sidebar'
import ChatPanel from './components/Chat/ChatPanel'
import PreviewPanel from './components/Preview/PreviewPanel'
import Composer from './components/Composer/Composer'
import ToastContainer from './components/Shared/ToastContainer'
import SettingsModal from './components/Shared/SettingsModal'
import ShortcutsModal from './components/Shared/ShortcutsModal'
import ResizablePanel from './components/Shared/ResizablePanel'
import PromptTemplatePicker from './components/Skills/PromptTemplatePicker'
import UndoSnackbar from './components/Shared/UndoSnackbar'
import ConnectorsPanel from './components/Skills/ConnectorsPanel'
import WelcomeTour from './components/Shared/WelcomeTour'
import { useUndo } from './hooks/useUndo'

export default function App() {
  const { settings, update: updateSettings } = useSettings()
  const { models, activeModel, switchModel } = useModels(settings.model)
  const { fileTree, selectedFile, fileContent, fileLanguage, loading: fileLoading, loadFileTree, openFile, closeFile } = useWorkspace()
  const { toasts, remove: removeToast, success: toastSuccess, error: toastError } = useToast()
  const { skills, activeSkill, switchSkill } = useSkills()
  const { undoItems, push: pushUndo, dismiss: dismissUndo } = useUndo()
  const { tags, getTagsFor, addTag, removeTag } = useTags()
  const [pinnedIds, setPinnedIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem('hiil_pinned') || '[]') } catch { return [] }
  })
  const [connectorsOpen, setConnectorsOpen] = useState(false)
  const [tourOpen, setTourOpen] = useState(() => {
    try { return localStorage.getItem('hiil_tour_complete') !== 'true' } catch { return true }
  })
  const [activeConversation, setActiveConversation] = useState(null)
  const [conversations, setConversations] = useState([])
  const [sidebarView, setSidebarView] = useState('conversations')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  const { messages, streaming, streamingText, ragChunks, activityLogs, error, send, stop, loadMessages, setMessages, editMessage, deleteMessage } = useChat(activeConversation?.id, pushUndo)

  useEffect(() => {
    loadConversations()
      .then(setConversations)
      .catch(err => { console.error('Failed to load conversations:', err); toastError('Failed to load conversations') })
    loadFileTree().catch(err => { console.error('Failed to load file tree:', err); toastError('Failed to load file tree') })
  }, [])

  useEffect(() => {
    if (activeConversation) {
      loadMessages().catch(err => { console.error('Failed to load messages:', err); toastError('Failed to load messages') })
    }
  }, [activeConversation?.id, loadMessages])

  useEffect(() => {
    document.documentElement.className = settings.theme === 'light' ? 'light' : ''
  }, [settings.theme])

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'k' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setShortcutsOpen(prev => !prev)
      }
      if (e.key === ',' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        setSettingsOpen(prev => !prev)
      }
      if (e.key === 'n' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        handleNewConversation()
      }
      if (e.key === '\\' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault()
        updateSettings({ sidebarVisible: !settings.sidebarVisible })
      }
      if (e.key === 'l' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
        e.preventDefault()
        setSidebarView('search')
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [settings.sidebarVisible, conversations.length])

  const style = {
    '--sidebar-width': `${settings.sidebarWidth}px`,
    '--preview-width': selectedFile ? `${settings.previewWidth}px` : '0px',
  }

  const handleNewConversation = useCallback(async () => {
    try {
      const id = await createConversation()
      const conv = { id, title: `Conversation ${conversations.length + 1}`, created: new Date().toISOString(), updated: new Date().toISOString(), message_count: 0, pinned: false }
      setConversations(prev => [conv, ...prev])
      setActiveConversation(conv)
      toastSuccess('New conversation created')
    } catch {
      toastError('Failed to create conversation')
    }
  }, [conversations.length])

  const handleTogglePin = useCallback((id) => {
    setPinnedIds(prev => {
      const next = prev.includes(id) ? prev.filter(pid => pid !== id) : [...prev, id]
      localStorage.setItem('hiil_pinned', JSON.stringify(next))
      return next
    })
    setConversations(prev => prev.map(c => c.id === id ? { ...c, pinned: !c.pinned } : c))
  }, [])

  const handleSelectConversation = useCallback((conv) => {
    setActiveConversation(conv)
  }, [])

  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeConversation?.id === id) setActiveConversation(null)
      toastSuccess('Conversation deleted')
    } catch {
      toastError('Failed to delete conversation')
    }
  }, [activeConversation])

  const handleRenameConversation = useCallback(async (id, title) => {
    try {
      await renameConversation(id, title)
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title } : c))
      if (activeConversation?.id === id) setActiveConversation(prev => prev ? { ...prev, title } : prev)
      toastSuccess('Conversation renamed')
    } catch {
      toastError('Failed to rename conversation')
    }
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

  const handleRetry = useCallback((msg) => {
    if (msg?.content) {
      setMessages(prev => prev.filter(m => m.id !== msg.id))
      send(msg.content)
    }
  }, [send, setMessages])

  const handleEditMessage = useCallback((msg, newText) => {
    editMessage(msg, newText)
  }, [editMessage])

  const handleDeleteMessage = useCallback((id) => {
    deleteMessage(id)
  }, [deleteMessage])

  const handleCopy = useCallback(() => {
    toastSuccess('Message copied to clipboard')
  }, [toastSuccess])

  const handleUndo = useCallback((item) => {
    if (item.undo) item.undo(item.data)
    toastSuccess('Undo successful')
  }, [toastSuccess])

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
        onToggleSidebar={() => updateSettings({ sidebarVisible: !settings.sidebarVisible })}
        settings={settings}
        onUpdateSettings={updateSettings}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenShortcuts={() => setShortcutsOpen(true)}
        activeSkill={activeSkill}
        onOpenSkills={() => setSidebarView('skills')}
        onOpenConnectors={() => setConnectorsOpen(true)}
      />
      <ResizablePanel side="left" defaultWidth={settings.sidebarWidth} minWidth={180} maxWidth={500} onWidthChange={(w) => updateSettings({ sidebarWidth: w })}>
        <Sidebar
          view={sidebarView}
          onViewChange={setSidebarView}
          conversations={conversations}
          activeConversation={activeConversation}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          fileTree={fileTree}
          onOpenFile={handleOpenFile}
          skills={skills}
          activeSkill={activeSkill}
          onSelectSkill={switchSkill}
          tags={tags}
          onAddTag={addTag}
          onRemoveTag={removeTag}
          onTogglePin={handleTogglePin}
        />
      </ResizablePanel>
      <ChatPanel
        messages={messages}
        streaming={streaming}
        streamingText={streamingText}
        ragChunks={ragChunks}
        activityLogs={activityLogs}
        error={error}
        activeConversation={activeConversation}
        onOpenFile={handleOpenFile}
        onRetry={handleRetry}
        onDelete={handleDeleteMessage}
        onCopy={handleCopy}
        onEdit={handleEditMessage}
        onExport={toastSuccess}
        activeSkill={activeSkill}
      />
      {selectedFile && (
        <ResizablePanel side="right" defaultWidth={settings.previewWidth} minWidth={240} maxWidth={800} onWidthChange={(w) => updateSettings({ previewWidth: w })}>
          <PreviewPanel
            filePath={selectedFile}
            content={fileContent}
            language={fileLanguage}
            loading={fileLoading}
            onClose={handleClosePreview}
            theme={settings.theme}
          />
        </ResizablePanel>
      )}
      <Composer
        streaming={streaming}
        onSend={handleSend}
        onStop={handleStop}
        onInsertTemplate
        templatePicker={<PromptTemplatePicker skill={activeSkill} />}
      />
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      {connectorsOpen && <div className="connectors-overlay"><ConnectorsPanel onClose={() => setConnectorsOpen(false)} /></div>}
      <UndoSnackbar items={undoItems} onUndo={handleUndo} onDismiss={dismissUndo} />
      {tourOpen && <WelcomeTour onComplete={() => setTourOpen(false)} />}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onUpdateSettings={updateSettings}
        models={models}
        activeModel={activeModel}
        onSwitchModel={switchModel}
      />
      <ShortcutsModal
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />
    </div>
  )
}
