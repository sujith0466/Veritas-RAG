import { create } from 'zustand'
import { notificationService, NotificationItem } from '@/services/notificationService'

interface InAppNotificationState {
  notifications: NotificationItem[]
  unreadCount: number
  total: number
  page: number
  pageSize: number
  loading: boolean
  error: string | null
}

interface InAppNotificationActions {
  fetchUnreadCount: () => Promise<void>
  fetchNotifications: (params?: { category?: string; unread_only?: boolean; page?: number; page_size?: number }) => Promise<void>
  markAsRead: (id: string) => Promise<void>
  markAllAsRead: () => Promise<void>
  dismissNotification: (id: string) => Promise<void>
  addIncomingNotification: (notification: NotificationItem) => void
  reset: () => void
}

const initialState: InAppNotificationState = {
  notifications: [],
  unreadCount: 0,
  total: 0,
  page: 1,
  pageSize: 20,
  loading: false,
  error: null,
}

export const useInAppNotificationStore = create<InAppNotificationState & InAppNotificationActions>()((set) => ({
  ...initialState,

  fetchUnreadCount: async () => {
    try {
      const res = await notificationService.getUnreadCount()
      set({ unreadCount: res.data.unread_count })
    } catch {
      // Graceful fallback
    }
  },

  fetchNotifications: async (params) => {
    set({ loading: true, error: null })
    try {
      const res = await notificationService.listNotifications(params)
      set({
        notifications: res.data.items,
        total: res.data.total,
        page: res.data.page,
        pageSize: res.data.page_size,
        unreadCount: res.data.unread_count,
        loading: false,
      })
    } catch (err: any) {
      set({
        loading: false,
        error: err?.response?.data?.detail || err.message || 'Failed to load notifications',
      })
    }
  },

  markAsRead: async (id: string) => {
    try {
      await notificationService.markAsRead(id)
      set((state) => {
        const updated = state.notifications.map((n) =>
          n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
        )
        const unreadCount = Math.max(0, state.unreadCount - 1)
        return { notifications: updated, unreadCount }
      })
    } catch {
      // Revert or ignore
    }
  },

  markAllAsRead: async () => {
    try {
      await notificationService.markAllAsRead()
      set((state) => ({
        notifications: state.notifications.map((n) => ({
          ...n,
          is_read: true,
          read_at: new Date().toISOString(),
        })),
        unreadCount: 0,
      }))
    } catch {
      // Revert or ignore
    }
  },

  dismissNotification: async (id: string) => {
    try {
      await notificationService.dismissNotification(id)
      set((state) => {
        const item = state.notifications.find((n) => n.id === id)
        const updated = state.notifications.filter((n) => n.id !== id)
        const unreadCount = item && !item.is_read ? Math.max(0, state.unreadCount - 1) : state.unreadCount
        return {
          notifications: updated,
          total: Math.max(0, state.total - 1),
          unreadCount,
        }
      })
    } catch {
      // Revert or ignore
    }
  },

  addIncomingNotification: (notification: NotificationItem) => {
    set((state) => {
      if (state.notifications.some((n) => n.id === notification.id)) {
        return state
      }
      return {
        notifications: [notification, ...state.notifications].slice(0, 50),
        unreadCount: notification.is_read ? state.unreadCount : state.unreadCount + 1,
        total: state.total + 1,
      }
    })
  },

  reset: () => set(initialState),
}))
