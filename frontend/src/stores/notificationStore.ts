import { create } from 'zustand'
import type { NotificationItem } from '@/types'

interface NotificationStoreState {
  notifications: NotificationItem[]
}

interface NotificationStoreActions {
  addNotification: (notification: Omit<NotificationItem, 'id'>) => string
  removeNotification: (id: string) => void
  clearAll: () => void
}

export const useNotificationStore = create<NotificationStoreState & NotificationStoreActions>()(
  (set) => ({
    notifications: [],

    addNotification: (notification) => {
      const id = crypto.randomUUID()
      set((state) => ({
        notifications: [...state.notifications, { ...notification, id }],
      }))
      return id
    },

    removeNotification: (id) =>
      set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id),
      })),

    clearAll: () => set({ notifications: [] }),
  }),
)
