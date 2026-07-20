import { useNotificationStore } from '@/stores/notificationStore'
import { useCallback } from 'react'

export function useToast() {
  const addNotification = useNotificationStore((state) => state.addNotification)
  const removeNotification = useNotificationStore((state) => state.removeNotification)

  const toast = useCallback(
    ({
      title,
      message,
      type = 'info',
      duration = 5000,
    }: {
      title: string
      message?: string
      type?: 'success' | 'error' | 'warning' | 'info'
      duration?: number
    }) => {
      const id = addNotification({ title, message, type, duration })

      if (duration > 0) {
        setTimeout(() => {
          removeNotification(id)
        }, duration)
      }

      return id
    },
    [addNotification, removeNotification],
  )

  const dismiss = useCallback(
    (id: string) => {
      removeNotification(id)
    },
    [removeNotification],
  )

  return { toast, dismiss }
}
