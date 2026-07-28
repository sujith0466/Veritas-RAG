import { create } from 'zustand'
import { apiClient as api } from '@/api/client'

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  message: string
  citations?: unknown[]
  reliability_score?: number
  metadata_json?: unknown
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
  setActiveSession: (session: ChatSession | null) => void
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSession: null,
  isLoading: false,

  fetchSessions: async () => {
    set({ isLoading: true })
    try {
      const { data } = await api.get('/chat/sessions')
      set({ sessions: data.data || [] })
    } catch (error) {
      console.error('Failed to fetch chat sessions', error)
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
      set({ activeSession: sessionData })
    } catch (error) {
      console.error('Failed to fetch chat session', error)
    }
  },

  createSession: async () => {
    const { data } = await api.post('/chat/sessions', { title: 'New Chat' })
    const newSession = data.data
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSession: newSession
    }))
    return newSession
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
    }
  },

  setActiveSession: (session) => set({ activeSession: session }),
}))
