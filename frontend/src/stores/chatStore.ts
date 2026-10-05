import { create } from 'zustand'
import { apiClient as api } from '@/api/client'
import { useNotificationStore } from '@/stores/notificationStore'

const notifyError = (title: string, message: string) => {
  const { addNotification, removeNotification } = useNotificationStore.getState()
  const id = addNotification({ title, message, type: 'error', duration: 5000 })
  setTimeout(() => removeNotification(id), 5000)
}

export interface ChatMessageMetadata {
  feedback?: 'like' | 'dislike' | null
  feedback_at?: string
  feedback_by?: string
  status?: string
  error?: unknown
  [key: string]: unknown
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  message: string
  citations?: unknown[]
  reliability_score?: number
  metadata_json?: ChatMessageMetadata | null
  created_at: string
}

export interface ChatSession {
  id: string
  tenant_id: string
  user_id: string
  title: string
  pinned: boolean
  archived: boolean
  created_at: string
  updated_at: string
  messages?: ChatMessage[]
}

interface ChatState {
  sessions: ChatSession[]
  activeSession: ChatSession | null
  isLoading: boolean
  fetchSessions: () => Promise<void>
  fetchSession: (id: string) => Promise<void>
  createSession: () => Promise<ChatSession>
  updateSession: (id: string, updates: Partial<ChatSession>) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  archiveSession: (id: string) => Promise<void>
  restoreSession: (id: string) => Promise<void>
  setActiveSession: (session: ChatSession | null) => void
  clearChatState: () => void
  hasMoreMessages: boolean
  messageOffset: number
  loadMoreMessages: (id: string) => Promise<void>
  rewindSession: (sessionId: string, messageId: string) => Promise<number>
  updateMessageFeedback: (sessionId: string, messageId: string, rating: 'like' | 'dislike' | null) => Promise<void>
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSession: null,
  isLoading: false,
  hasMoreMessages: false,
  messageOffset: 0,

  fetchSessions: async () => {
    set({ isLoading: true })
    try {
      const { data } = await api.get('/chat/sessions')
      set({ sessions: data.data || [] })
    } catch (error) {
      console.error('Failed to fetch chat sessions', error)
      notifyError('Fetch Failed', (error as Error).message || 'Failed to fetch chat sessions')
    } finally {
      set({ isLoading: false })
    }
  },

  fetchSession: async (id: string) => {
    try {
      const [sessionRes, messagesRes] = await Promise.all([
        api.get(`/chat/sessions/${id}`),
        api.get(`/chat/sessions/${id}/messages?limit=100`)
      ])
      const sessionData = sessionRes.data.data
      sessionData.messages = messagesRes.data.data || []
      set({ 
        activeSession: sessionData,
        hasMoreMessages: sessionData.messages.length >= 100,
        messageOffset: sessionData.messages.length
      })
    } catch (error) {
      console.error('Failed to fetch chat session', error)
      set({ activeSession: null })
      notifyError('Fetch Failed', (error as Error).message || 'Failed to fetch chat session')
      throw error
    }
  },

  loadMoreMessages: async (id: string) => {
    const state = useChatStore.getState()
    if (!state.hasMoreMessages || !state.activeSession || state.activeSession.id !== id) return
    
    try {
      const { data } = await api.get(`/chat/sessions/${id}/messages?limit=100&offset=${state.messageOffset}`)
      const newMessages = data.data || []
      
      set((prev) => {
        if (!prev.activeSession || prev.activeSession.id !== id) return prev
        return {
          activeSession: {
            ...prev.activeSession,
            messages: [...newMessages, ...(prev.activeSession.messages || [])]
          },
          messageOffset: prev.messageOffset + newMessages.length,
          hasMoreMessages: newMessages.length >= 100
        }
      })
    } catch (error) {
      console.error('Failed to load more messages', error)
      notifyError('Load Failed', 'Failed to load historical messages')
      set({ hasMoreMessages: false })
    }
  },

  createSession: async () => {
    try {
      const { data } = await api.post('/chat/sessions', { title: 'New Chat' })
      const newSession = data.data
      set((state) => ({
        sessions: [newSession, ...state.sessions],
        activeSession: newSession
      }))
      return newSession
    } catch (error) {
      notifyError('Create Failed', (error as Error).message || 'Failed to create session')
      throw error
    }
  },

  updateSession: async (id: string, updates: Partial<ChatSession>) => {
    try {
      const { data } = await api.put(`/chat/sessions/${id}`, updates)
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === id ? { ...s, ...data.data } : s)),
        activeSession: state.activeSession?.id === id ? { ...state.activeSession, ...data.data } : state.activeSession
      }))
    } catch (error) {
      console.error('Failed to update session', error)
      notifyError('Update Failed', (error as Error).message || 'Failed to update session')
    }
  },

  deleteSession: async (id: string) => {
    try {
      await api.delete(`/chat/sessions/${id}`)
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== id),
        activeSession: state.activeSession?.id === id ? null : state.activeSession
      }))
    } catch (error) {
      console.error('Failed to delete session', error)
      notifyError('Delete Failed', (error as Error).message || 'Failed to delete session')
    }
  },

  archiveSession: async (id: string) => {
    try {
      await api.put(`/chat/sessions/${id}`, { archived: true })
      set((state) => ({
        sessions: state.sessions.filter((s) => s.id !== id),
        activeSession: state.activeSession?.id === id ? null : state.activeSession
      }))
    } catch (error) {
      console.error('Failed to archive session', error)
      notifyError('Archive Failed', (error as Error).message || 'Failed to archive session')
    }
  },

  restoreSession: async (id: string) => {
    try {
      const { data } = await api.put(`/chat/sessions/${id}`, { archived: false })
      set((state) => ({
        sessions: [data.data, ...state.sessions].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      }))
    } catch (error) {
      console.error('Failed to restore session', error)
      notifyError('Restore Failed', (error as Error).message || 'Failed to restore session')
    }
  },

  setActiveSession: (session) => set({ activeSession: session }),
  clearChatState: () =>
    set({
      sessions: [],
      activeSession: null,
      hasMoreMessages: false,
      messageOffset: 0,
      isLoading: false,
    }),

  rewindSession: async (sessionId: string, messageId: string) => {
    try {
      const { data } = await api.post(`/chat/sessions/${sessionId}/messages/${messageId}/rewind`)
      const deletedCount = data.data?.deleted_count ?? 0

      // Truncate local activeSession messages up to messageId (exclusive)
      set((state) => {
        if (!state.activeSession || state.activeSession.id !== sessionId || !state.activeSession.messages) {
          return state
        }
        const msgs = state.activeSession.messages
        const targetIdx = msgs.findIndex((m) => m.id === messageId)
        if (targetIdx === -1) return state

        return {
          activeSession: {
            ...state.activeSession,
            messages: msgs.slice(0, targetIdx)
          }
        }
      })

      return deletedCount
    } catch (error) {
      console.error('Failed to rewind session', error)
      notifyError('Rewind Failed', (error as Error).message || 'Failed to rewind session')
      throw error
    }
  },

  updateMessageFeedback: async (sessionId: string, messageId: string, rating: 'like' | 'dislike' | null) => {
    const state = useChatStore.getState()
    const active = state.activeSession
    let previousFeedback: 'like' | 'dislike' | null = null

    // 1. Optimistic local update
    if (active && active.id === sessionId && active.messages) {
      const target = active.messages.find((m) => m.id === messageId)
      if (target) {
        previousFeedback = (target.metadata_json as ChatMessageMetadata)?.feedback || null
      }

      set((s) => {
        if (!s.activeSession || s.activeSession.id !== sessionId || !s.activeSession.messages) return s
        return {
          activeSession: {
            ...s.activeSession,
            messages: s.activeSession.messages.map((m) => {
              if (m.id !== messageId) return m
              const meta: ChatMessageMetadata = { ...(m.metadata_json || {}) }
              if (rating === null) {
                delete meta.feedback
                delete meta.feedback_at
                delete meta.feedback_by
              } else {
                meta.feedback = rating
                meta.feedback_at = new Date().toISOString()
              }
              return { ...m, metadata_json: meta }
            })
          }
        }
      })
    }

    // 2. Server persistence
    try {
      await api.put(`/chat/sessions/${sessionId}/messages/${messageId}/feedback`, { rating })
    } catch (error) {
      console.error('Failed to update feedback', error)
      notifyError('Feedback Failed', 'Could not save feedback')
      // Rollback optimistic update
      set((s) => {
        if (!s.activeSession || s.activeSession.id !== sessionId || !s.activeSession.messages) return s
        return {
          activeSession: {
            ...s.activeSession,
            messages: s.activeSession.messages.map((m) => {
              if (m.id !== messageId) return m
              const meta: ChatMessageMetadata = { ...(m.metadata_json || {}) }
              if (previousFeedback === null) {
                delete meta.feedback
                delete meta.feedback_at
                delete meta.feedback_by
              } else {
                meta.feedback = previousFeedback
              }
              return { ...m, metadata_json: meta }
            })
          }
        }
      })
      throw error
    }
  },
}))
