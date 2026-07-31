import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react'
import { useChat } from '../hooks/useChat'
import { useTags } from '../hooks/useTags'
import { useUndo } from '../hooks/useUndo'
import { loadConversations, createConversation, deleteConversation, renameConversation } from '../api/chat'
import { useUIContext } from './UIContext'

const LIMIT = 50

const ChatContext = createContext(null)

export function ChatProvider({ children }) {
  const { toastSuccess, toastError } = useChatContextDeps()
  const [activeConversation, setActiveConversation] = useState(null)
  const [conversations, setConversations] = useState([])
  const [conversationsLoading, setConversationsLoading] = useState(true)
  const [scrollToMessageId, setScrollToMessageId] = useState(null)
  const [pinnedIds, setPinnedIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem('hiil_pinned') || '[]') } catch { return [] }
  })
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  const { tags, addTag, removeTag } = useTags()
  const { undoItems, push: pushUndo, dismiss: dismissUndo } = useUndo()
  const { messages, streaming, streamingText, ragChunks, activityLogs, error, send, stop, loadMessages, setMessages, editMessage, deleteMessage } = useChat(activeConversation?.id, pushUndo)

  const prevMessagesLength = useRef(0)

  useEffect(() => {
    setConversationsLoading(true)
    loadConversations({ limit: LIMIT, offset: 0 })
      .then(({ conversations: items }) => {
        setConversations(items)
        setHasMore(items.length >= LIMIT)
        setOffset(items.length)
      })
      .catch(err => { console.error('Failed to load conversations:', err); toastError?.('Failed to load conversations') })
      .finally(() => setConversationsLoading(false))
  }, [])

  useEffect(() => {
    if (activeConversation) {
      loadMessages().catch(err => { console.error('Failed to load messages:', err); toastError?.('Failed to load messages') })
    }
  }, [activeConversation?.id])

  useEffect(() => {
    if (!scrollToMessageId || messages.length === 0) return
    if (messages.length === prevMessagesLength.current) return
    prevMessagesLength.current = messages.length
    const id = `msg-${scrollToMessageId}`
    requestAnimationFrame(() => {
      const el = document.getElementById(id)
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el.classList.add('search-highlight')
        setTimeout(() => el.classList.remove('search-highlight'), 2500)
      }
      setScrollToMessageId(null)
    })
  }, [messages, scrollToMessageId])

  const _createConversation = useCallback(async () => {
    const id = await createConversation()
    const conv = { id, title: `Conversation ${conversations.length + 1}`, created: new Date().toISOString(), updated: new Date().toISOString(), message_count: 0, pinned: false }
    return conv
  }, [conversations.length])

  const handleNewConversation = useCallback(async () => {
    try {
      const conv = await _createConversation()
      setConversations(prev => [conv, ...prev])
      setActiveConversation(conv)
      toastSuccess?.('New conversation created')
    } catch {
      toastError?.('Failed to create conversation')
    }
  }, [_createConversation])

  const handleSelectConversation = useCallback((conv) => {
    setActiveConversation(conv)
    setScrollToMessageId(null)
  }, [])

  const handleSearchResultClick = useCallback((conv, messageId) => {
    setActiveConversation(conv)
    setScrollToMessageId(messageId)
  }, [])

  const handleDeleteConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeConversation?.id === id) setActiveConversation(null)
      toastSuccess?.('Conversation deleted')
    } catch {
      toastError?.('Failed to delete conversation')
    }
  }, [activeConversation])

  const handleRenameConversation = useCallback(async (id, title) => {
    try {
      await renameConversation(id, title)
      setConversations(prev => prev.map(c => c.id === id ? { ...c, title } : c))
      if (activeConversation?.id === id) setActiveConversation(prev => prev ? { ...prev, title } : prev)
      toastSuccess?.('Conversation renamed')
    } catch {
      toastError?.('Failed to rename conversation')
    }
  }, [activeConversation])

  const handleTogglePin = useCallback((id) => {
    setPinnedIds(prev => {
      const next = prev.includes(id) ? prev.filter(pid => pid !== id) : [...prev, id]
      localStorage.setItem('hiil_pinned', JSON.stringify(next))
      return next
    })
    setConversations(prev => prev.map(c => c.id === id ? { ...c, pinned: !c.pinned } : c))
  }, [])

  const handleSend = useCallback(async (text, images) => {
    if (streaming) return
    try {
      let cid = activeConversation?.id
      if (!cid) {
        const conv = await _createConversation()
        setConversations(prev => [conv, ...prev])
        setActiveConversation(conv)
        cid = conv.id
      }
      await send(text, images, cid)
    } catch (err) {
      toastError?.(err?.message || 'Failed to send message')
    }
  }, [send, streaming, toastError, activeConversation?.id, _createConversation])

  const handleRetry = useCallback((msg) => {
    if (msg?.content) {
      setMessages(prev => prev.filter(m => m.id !== msg.id))
      send(msg.content)
    }
  }, [send, setMessages])

  const handleCopy = useCallback(() => {
    toastSuccess?.('Message copied to clipboard')
  }, [toastSuccess])

  const handleUndo = useCallback((item) => {
    if (item.undo) item.undo(item.data)
    toastSuccess?.('Undo successful')
  }, [toastSuccess])

  const loadMoreConversations = useCallback(async () => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)
    try {
      const { conversations: items } = await loadConversations({ limit: LIMIT, offset })
      setConversations(prev => [...prev, ...items])
      setOffset(prev => prev + items.length)
      setHasMore(items.length >= LIMIT)
    } catch {
      toastError?.('Failed to load more conversations')
    } finally {
      setLoadingMore(false)
    }
  }, [offset, hasMore, loadingMore])

  const value = {
    conversations, conversationsLoading, activeConversation,
    messages, streaming, streamingText, ragChunks, activityLogs, error,
    pinnedIds, tags, addTag, removeTag,
    undoItems, dismissUndo,
    scrollToMessageId,
    hasMore, loadingMore,
    handleNewConversation, handleSelectConversation,
    handleSearchResultClick,
    handleDeleteConversation, handleRenameConversation, handleTogglePin,
    handleSend, handleEditMessage: editMessage, handleDeleteMessage: deleteMessage,
    handleRetry, handleStop: stop, handleCopy, handleUndo,
    loadMoreConversations,
  }

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}

function useChatContextDeps() {
  try {
    const ui = useUIContext()
    return { toastSuccess: ui.toastSuccess, toastError: ui.toastError }
  } catch {
    return { toastSuccess: () => {}, toastError: () => {} }
  }
}

export function useChatContext() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChatContext must be used within ChatProvider')
  return ctx
}
