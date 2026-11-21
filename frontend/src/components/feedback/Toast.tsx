import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'
import { useNotificationStore } from '@/stores/notificationStore'
import {
  dynamicIslandVariants,
  dynamicIslandContentVariants,
  dynamicIslandPillVariants,
} from '@/motion'
import { cn } from '@/utils/cn'
import type { NotificationItem } from '@/types'

const statusMap = {
  success: {
    icon: CheckCircle2,
    badgeBg: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    dotBg: 'bg-emerald-500',
    pillText: 'Success',
  },
  error: {
    icon: AlertCircle,
    badgeBg: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
    dotBg: 'bg-rose-500',
    pillText: 'Alert',
  },
  warning: {
    icon: AlertTriangle,
    badgeBg: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    dotBg: 'bg-amber-500',
    pillText: 'Warning',
  },
  info: {
    icon: Info,
    badgeBg: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20',
    dotBg: 'bg-sky-500',
    pillText: 'Notice',
  },
}

/**
 * Counts genuinely open dialogs and modal drawers in the DOM.
 * Keeps suppression active while Radix dialogs or custom modals exist in the DOM,
 * including during Radix exit animations, fulfilling visual acceptance conditions.
 */
export function getActiveModalCount(): number {
  if (typeof document === 'undefined') return 0

  const candidates = document.querySelectorAll<HTMLElement>(
    '[role="dialog"], [role="alertdialog"], dialog'
  )

  let count = 0
  for (let i = 0; i < candidates.length; i++) {
    const el = candidates[i]

    // 1. Exclude the Dynamic Island itself
    if (el.hasAttribute('data-dynamic-island')) {
      continue
    }

    // 2. Exclude elements explicitly hidden via HTML hidden attribute
    if (el.hasAttribute('hidden')) {
      continue
    }

    // 3. Exclude elements with display: none or visibility: hidden
    if (el.style.display === 'none' || el.style.visibility === 'hidden') {
      continue
    }

    // 4. Exclude native HTML dialog elements that are not open
    if (el instanceof HTMLDialogElement && !el.open) {
      continue
    }

    count++
  }
  return count
}

interface DynamicIslandItemProps {
  notification: NotificationItem
  onDismissComplete: (id: string) => void
}

function DynamicIslandItem({ notification, onDismissComplete }: DynamicIslandItemProps) {
  const [stage, setStage] = useState<'pill' | 'expanded' | 'collapsing'>('pill')
  const [isSuppressed, setIsSuppressed] = useState(false)
  const [isStableReadable, setIsStableReadable] = useState(false)

  const isDismissedRef = useRef(false)
  const isCountdownCompletedRef = useRef(false)
  const isSuppressedRef = useRef(false)
  const timerRef = useRef<NodeJS.Timeout | null>(null)
  const pillDwellTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const startTimeRef = useRef<number | null>(null)
  const remainingTimeRef = useRef<number>(notification.duration ?? 5000)

  const status = statusMap[notification.type] || statusMap.info
  const Icon = status.icon
  const hasMessage = Boolean(notification.message && notification.message.trim().length > 0)

  // Authoritative 3-tier target priority:
  // 1. collapsing (terminal dismissal)
  // 2. suppressed (modal suppression)
  // 3. normal presentation stage (pill -> expanded)
  const targetVariant = isDismissedRef.current || stage === 'collapsing'
    ? 'collapsing'
    : isSuppressed
      ? 'suppressed'
      : stage

  const targetVariantRef = useRef(targetVariant)
  targetVariantRef.current = targetVariant

  // Unified dismiss handler (timeout or manual)
  const handleDismiss = useCallback((_reason: 'timeout' | 'manual') => {
    if (isDismissedRef.current) return
    isDismissedRef.current = true

    if (pillDwellTimeoutRef.current) {
      clearTimeout(pillDwellTimeoutRef.current)
      pillDwellTimeoutRef.current = null
    }

    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    startTimeRef.current = null
    isCountdownCompletedRef.current = true
    setIsStableReadable(false)

    setStage('collapsing')
  }, [])

  // Cleanup pending dwell timers on unmount
  useEffect(() => {
    return () => {
      if (pillDwellTimeoutRef.current) {
        clearTimeout(pillDwellTimeoutRef.current)
        pillDwellTimeoutRef.current = null
      }
    }
  }, [])

  // Modal detection via MutationObserver with synchronous ref mirror
  useEffect(() => {
    const updateSuppression = () => {
      const activeCount = getActiveModalCount()
      const shouldSuppress = activeCount > 0

      isSuppressedRef.current = shouldSuppress

      if (shouldSuppress) {
        setIsStableReadable(false)
      }

      setIsSuppressed(shouldSuppress)
    }

    updateSuppression()

    const observer = new MutationObserver(updateSuppression)
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-state', 'hidden', 'open', 'style'],
    })

    return () => observer.disconnect()
  }, [])

  // Animation completion handler with target-variant guard
  const handleAnimationComplete = (definition: string) => {
    if (definition !== targetVariantRef.current) {
      return
    }

    if (definition === 'pill') {
      // Stage 1 Dwell: keep compact horizontal capsule intentionally settled before expanding
      if (pillDwellTimeoutRef.current) clearTimeout(pillDwellTimeoutRef.current)
      pillDwellTimeoutRef.current = setTimeout(() => {
        if (!isDismissedRef.current && !isSuppressedRef.current) {
          setStage('expanded')
        }
      }, 380)
    } else if (definition === 'expanded') {
      // Direct synchronous DOM query protects against microtask delivery latency
      const isModalActive = isSuppressedRef.current || getActiveModalCount() > 0
      if (!isModalActive && !isDismissedRef.current) {
        setIsStableReadable(true)
      }
    } else if (definition === 'collapsing') {
      onDismissComplete(notification.id)
    }
  }

  // Authoritative Display Timer Controller
  useEffect(() => {
    if (!isStableReadable || isDismissedRef.current || isCountdownCompletedRef.current) {
      return
    }

    const configuredDuration = notification.duration ?? 5000
    // Duration-zero persistent notification
    if (configuredDuration === 0) {
      return
    }

    if (remainingTimeRef.current <= 0) {
      handleDismiss('timeout')
      return
    }

    startTimeRef.current = Date.now()

    timerRef.current = setTimeout(() => {
      isCountdownCompletedRef.current = true
      timerRef.current = null
      startTimeRef.current = null
      remainingTimeRef.current = 0
      handleDismiss('timeout')
    }, remainingTimeRef.current)

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }

      if (!isCountdownCompletedRef.current && startTimeRef.current !== null) {
        const elapsed = Date.now() - startTimeRef.current
        remainingTimeRef.current = Math.max(0, remainingTimeRef.current - elapsed)
        startTimeRef.current = null
      }
    }
  }, [isStableReadable, notification.id, notification.duration, handleDismiss])

  return (
    <motion.div
      data-dynamic-island="true"
      role="alert"
      aria-live="polite"
      variants={dynamicIslandVariants}
      custom={{ hasMessage }}
      initial="initial"
      animate={targetVariant}
      onAnimationComplete={handleAnimationComplete}
      className={cn(
        'pointer-events-auto relative overflow-hidden',
        'w-auto max-w-[calc(100vw-2rem)] sm:max-w-md',
        'bg-surface-elevated/95 dark:bg-[#0c0e14]/95 text-foreground dark:text-white',
        'border border-border/80 dark:border-white/10',
        'shadow-[0_16px_40px_-8px_rgba(0,0,0,0.2),0_4px_16px_-4px_rgba(0,0,0,0.1)]',
        'dark:shadow-[0_16px_40px_-8px_rgba(0,0,0,0.7),0_4px_16px_-4px_rgba(0,0,0,0.4)]',
        'backdrop-blur-2xl transition-colors duration-200'
      )}
    >
      {/* Stage 1: Compact Horizontal Capsule View */}
      <motion.div
        variants={dynamicIslandPillVariants}
        initial="initial"
        animate={targetVariant}
        className={cn(
          'flex h-[38px] items-center justify-center gap-2 px-3.5 select-none',
          stage === 'pill' ? 'pointer-events-auto' : 'pointer-events-none absolute inset-0'
        )}
        aria-hidden={stage !== 'pill'}
      >
        <span className={cn('h-2 w-2 rounded-full animate-pulse shrink-0', status.dotBg)} />
        <span className="text-xs font-semibold tracking-wide text-foreground dark:text-white/90 whitespace-nowrap">
          {status.pillText}
        </span>
      </motion.div>

      {/* Stage 2 & 3: Expanded Dynamic Island Card View */}
      <motion.div
        variants={dynamicIslandContentVariants}
        initial="initial"
        animate={targetVariant}
        className={cn(
          'gap-2.5 sm:gap-3',
          hasMessage
            ? 'flex items-start p-3.5 sm:p-4'
            : 'flex items-center py-2.5 px-3.5 sm:py-2.5 sm:px-4',
          stage === 'pill' ? 'pointer-events-none invisible absolute inset-0' : 'pointer-events-auto'
        )}
        aria-hidden={stage === 'pill'}
      >
        <div
          className={cn(
            'rounded-full p-1.5 border shrink-0',
            hasMessage && 'mt-0.5',
            status.badgeBg
          )}
        >
          <Icon className="h-4 w-4" />
        </div>

        <div className="flex-1 min-w-0 pr-1">
          <p
            className={cn(
              'text-sm font-semibold text-foreground dark:text-white break-words',
              hasMessage ? 'leading-snug' : 'leading-tight'
            )}
          >
            {notification.title}
          </p>
          {hasMessage && (
            <p className="mt-1 text-xs text-muted-foreground dark:text-neutral-400 leading-relaxed break-words">
              {notification.message}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => handleDismiss('manual')}
          aria-label="Dismiss notification"
          className="rounded-full p-1 text-muted-foreground hover:text-foreground dark:text-neutral-400 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary shrink-0 opacity-70 hover:opacity-100"
        >
          <X className="h-4 w-4" />
        </button>
      </motion.div>
    </motion.div>
  )
}

/**
 * Backward compatibility alias for single toast presentation
 */
export function Toast({ notification }: { notification: NotificationItem }) {
  const removeNotification = useNotificationStore((state) => state.removeNotification)
  return <DynamicIslandItem notification={notification} onDismissComplete={removeNotification} />
}

/**
 * Master Dynamic Island Container.
 * Positioned fixed top-center, manages single-active-notification FIFO queue with AnimatePresence mode="wait".
 */
export function ToastContainer() {
  const notifications = useNotificationStore((state) => state.notifications)
  const removeNotification = useNotificationStore((state) => state.removeNotification)

  // Single-active-notification FIFO policy
  const activeNotification = notifications.length > 0 ? notifications[0] : null

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed top-20 sm:top-[84px] left-1/2 -translate-x-1/2 z-[700] flex flex-col items-center justify-start w-full max-w-md px-4 sm:px-0"
    >
      <AnimatePresence mode="wait">
        {activeNotification && (
          <DynamicIslandItem
            key={activeNotification.id}
            notification={activeNotification}
            onDismissComplete={removeNotification}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
