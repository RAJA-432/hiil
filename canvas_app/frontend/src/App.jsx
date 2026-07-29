import { useEffect, lazy, Suspense } from 'react'
import { ChatProvider, useChatContext } from './context/ChatContext'
import { UIProvider, useUIContext } from './context/UIContext'
import Toolbar from './components/Toolbar/Toolbar'
import Sidebar from './components/Sidebar/Sidebar'
import ChatPanel from './components/Chat/ChatPanel'
const PreviewPanel = lazy(() => import('./components/Preview/PreviewPanel'))
import Composer from './components/Composer/Composer'
import ToastContainer from './components/Shared/ToastContainer'
const SettingsModal = lazy(() => import('./components/Shared/SettingsModal'))
const ShortcutsModal = lazy(() => import('./components/Shared/ShortcutsModal'))
import ResizablePanel from './components/Shared/ResizablePanel'
import PromptTemplatePicker from './components/Skills/PromptTemplatePicker'
import UndoSnackbar from './components/Shared/UndoSnackbar'
const ConnectorsPanel = lazy(() => import('./components/Skills/ConnectorsPanel'))
import WelcomeTour from './components/Shared/WelcomeTour'

function AppInner() {
  const { settings, updateSettings, sidebarView, setSidebarView, settingsOpen, setSettingsOpen, shortcutsOpen, setShortcutsOpen, connectorsOpen, setConnectorsOpen, tourOpen, setTourOpen, selectedFile, fileContent, fileLanguage, fileLoading, toasts, removeToast, toastSuccess, toastError, activeSkill, handleSwitchModel, handleSelectSkill, openFile, closeFile } = useUIContext()
  const { conversations, streaming, handleNewConversation, handleSend, handleStop, undoItems, dismissUndo, handleUndo, handleCopy } = useChatContext()

  useEffect(() => {
    document.documentElement.className = settings.theme === 'light' ? 'light' : ''
  }, [settings.theme])

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'k' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); setShortcutsOpen(v => !v) }
      if (e.key === ',' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); setSettingsOpen(v => !v) }
      if (e.key === 'n' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); handleNewConversation() }
      if (e.key === '\\' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); updateSettings({ sidebarVisible: !settings.sidebarVisible }) }
      if (e.key === 'l' && (e.ctrlKey || e.metaKey) && !e.shiftKey) { e.preventDefault(); setSidebarView('search') }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [settings.sidebarVisible, conversations.length])

  const style = {
    '--sidebar-width': `${settings.sidebarWidth}px`,
    '--preview-width': selectedFile ? `${settings.previewWidth}px` : '0px',
  }

  const layoutClass = [
    'canvas-layout',
    !selectedFile && 'preview-hidden',
    !settings.sidebarVisible && 'sidebar-hidden',
  ].filter(Boolean).join(' ')

  return (
    <div className={layoutClass} style={style}>
      <Toolbar />
      <ResizablePanel side="left" defaultWidth={settings.sidebarWidth} minWidth={180} maxWidth={500} onWidthChange={(w) => updateSettings({ sidebarWidth: w })}>
        <Sidebar />
      </ResizablePanel>
      <ChatPanel onOpenFile={openFile} onCopy={handleCopy} />
      {selectedFile && (
        <ResizablePanel side="right" defaultWidth={settings.previewWidth} minWidth={240} maxWidth={800} onWidthChange={(w) => updateSettings({ previewWidth: w })}>
          <Suspense fallback={<div className="preview-loading">Loading preview...</div>}>
            <PreviewPanel filePath={selectedFile} content={fileContent} language={fileLanguage} loading={fileLoading} onClose={closeFile} theme={settings.theme} />
          </Suspense>
        </ResizablePanel>
      )}
      <Composer streaming={streaming} onSend={handleSend} onStop={handleStop} onInsertTemplate={() => {}} templatePicker={<PromptTemplatePicker skill={activeSkill} />} />
      <ToastContainer />
      {connectorsOpen && <div className="connectors-overlay"><Suspense fallback={null}><ConnectorsPanel onClose={() => setConnectorsOpen(false)} /></Suspense></div>}
      <UndoSnackbar />
      {tourOpen && <WelcomeTour onComplete={() => setTourOpen(false)} />}
      <Suspense fallback={null}><SettingsModal /></Suspense>
      <Suspense fallback={null}><ShortcutsModal /></Suspense>
    </div>
  )
}

export default function App() {
  return (
    <UIProvider>
      <ChatProvider>
        <AppInner />
      </ChatProvider>
    </UIProvider>
  )
}
