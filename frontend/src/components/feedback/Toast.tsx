import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'
import { useNotificationStore } from '@/stores/notificationStore'
import { toastVariants } from '@/motion'
import { cn } from '@/utils/cn'
import type { NotificationItem } from '@/types'

const iconMap = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
}

const colorMap = {
  success: 'bg-surface border-success/30 text-success',
  error: 'bg-surface border-danger/30 text-danger',
  warning: 'bg-surface border-warning/30 text-warning',
  info: 'bg-surface border-info/30 text-info',
}

function Toast({ notification }: { notification: NotificationItem }) {
  const removeNotification = useNotificationStore((state) => state.removeNotification)
  const Icon = iconMap[notification.type]

  useEffect(() => {
    if (notification.duration && notification.duration > 0) {
      const timer = setTimeout(() => {
        removeNotification(notification.id)
      }, notification.duration)
      return () => clearTimeout(timer)
    }
  }, [notification, removeNotification])

  return (
    <motion.div
      variants={toastVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      layout
      className={cn(
        'pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border p-4 shadow-lg backdrop-blur-sm',
        colorMap[notification.type],
      )}
      role="alert"
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="flex-1 space-y-1">
        <p className="text-sm font-medium leading-none text-foreground">
          {notification.title}
        </p>
        {notification.message && (
          <p className="text-sm text-muted-foreground">{notification.message}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => removeNotification(notification.id)}
        className="text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-sm shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </button>
    </motion.div>
  )
}

export function ToastContainer() {
  const notifications = useNotificationStore((state) => state.notifications)

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-0 right-0 z-[700] flex max-h-screen w-full flex-col-reverse gap-2 p-4 sm:bottom-0 sm:right-0 sm:flex-col sm:p-6 md:max-w-[420px]"
    >
      <AnimatePresence mode="popLayout">
        {notifications.map((notification) => (
          <Toast key={notification.id} notification={notification} />
        ))}
      </AnimatePresence>
    </div>
  )
}
