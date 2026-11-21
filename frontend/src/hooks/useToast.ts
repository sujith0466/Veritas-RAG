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
      return addNotification({ title, message, type, duration })
    },
    [addNotification],
  )

  const dismiss = useCallback(
    (id: string) => {
      removeNotification(id)
    },
    [removeNotification],
  )

  return { toast, dismiss }
}
