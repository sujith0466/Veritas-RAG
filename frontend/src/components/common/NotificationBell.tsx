import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCheck, ExternalLink, ShieldAlert, FileText, Settings, Info, AlertTriangle, AlertCircle, Trash2 } from 'lucide-react'
import { Button } from './Button'
import { Card } from './Card'
import { useAuthStore } from '@/stores/authStore'
import { useInAppNotificationStore } from '@/stores/inAppNotificationStore'
import { NotificationItem } from '@/services/notificationService'
import { cn } from '@/utils/cn'

export function NotificationBell() {
  const [isOpen, setIsOpen] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const token = useAuthStore((s) => s.token)
  const {
    notifications,
    unreadCount,
    fetchUnreadCount,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    dismissNotification,
    addIncomingNotification,
  } = useInAppNotificationStore()

  // 1. Initial REST Hydration
  useEffect(() => {
    if (token) {
      fetchUnreadCount()
    }
  }, [token, fetchUnreadCount])

  // 2. Fetch full list when popover opens
  useEffect(() => {
    if (isOpen && token) {
      fetchNotifications({ page: 1, page_size: 15 })
    }
  }, [isOpen, token, fetchNotifications])

  // 3. WebSocket Real-time Push
  useEffect(() => {
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/notifications/ws?token=${token}`

    let ws: WebSocket | null = null
    try {
      ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          const item: NotificationItem = {
            id: data.id || crypto.randomUUID(),
            tenant_id: data.tenant_id || '',
            user_id: data.user_id || null,
            category: data.category || 'SYSTEM',
            severity: data.severity || 'INFO',
            title: data.title || data.type || 'Notification',
            message: data.message || (data.payload ? JSON.stringify(data.payload) : ''),
            action_url: data.action_url || null,
            payload_json: data.payload || null,
            is_read: false,
            read_at: null,
            created_at: data.timestamp || new Date().toISOString(),
          }
          addIncomingNotification(item)
        } catch (err) {
          console.error('Failed to parse incoming notification event', err)
        }
      }
    } catch (e) {
      console.warn('Failed to establish notification WebSocket', e)
    }

    return () => {
      if (ws) {
        ws.close()
      }
    }
  }, [token, addIncomingNotification])

  const toggleOpen = () => {
    setIsOpen(!isOpen)
  }

  const getCategoryIcon = (category: string, severity: string) => {
    if (severity === 'CRITICAL' || severity === 'ERROR') {
      return <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
    }
    if (severity === 'WARNING') {
      return <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
    }
    switch (category) {
      case 'SECURITY':
        return <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0" />
      case 'DOCUMENT':
        return <FileText className="w-4 h-4 text-blue-500 shrink-0" />
      case 'WORKSPACE':
        return <Settings className="w-4 h-4 text-purple-500 shrink-0" />
      default:
        return <Info className="w-4 h-4 text-primary shrink-0" />
    }
  }

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleOpen}
        aria-label="Open notifications"
        className="group relative h-9 w-9 rounded-lg border border-transparent hover:border-border/60 hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:border-transparent active:scale-95"
      >
        <Bell className="w-4.5 h-4.5 transition-transform duration-200 group-hover:rotate-12 motion-reduce:group-hover:rotate-0" />
        {unreadCount > 0 && (
          <span
            data-testid="unread-badge"
            className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-bold text-white shadow-sm ring-2 ring-background animate-in zoom-in-75"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </Button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <Card
            data-testid="notification-popover"
            className="absolute right-0 mt-2 w-84 sm:w-96 max-h-[480px] flex flex-col z-50 shadow-xl border border-border/80 bg-background/98 backdrop-blur-md animate-in fade-in slide-in-from-top-2 overflow-hidden"
          >
            {/* Popover Header */}
            <div className="p-3.5 border-b border-border bg-card/60 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-sm text-foreground">Notifications</h3>
                {unreadCount > 0 && (
                  <span className="text-[11px] font-medium bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                    {unreadCount} unread
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                {unreadCount > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => markAllAsRead()}
                    className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/60"
                    title="Mark all as read"
                  >
                    <CheckCheck className="w-3.5 h-3.5 mr-1" />
                    Read all
                  </Button>
                )}
              </div>
            </div>

            {/* Notification List */}
            <div className="flex-1 overflow-y-auto divide-y divide-border/60">
              {notifications.length === 0 ? (
                <div className="p-10 text-center text-muted-foreground text-sm flex flex-col items-center justify-center gap-2">
                  <Bell className="w-8 h-8 text-muted-foreground/40 stroke-[1.5]" />
                  <p className="text-sm font-medium">All caught up!</p>
                  <p className="text-xs text-muted-foreground/70">No notifications to display right now.</p>
                </div>
              ) : (
                notifications.slice(0, 15).map((n) => (
                  <div
                    key={n.id}
                    className={cn(
                      'p-3.5 text-sm transition-colors hover:bg-muted/40 flex items-start gap-3 group relative',
                      !n.is_read && 'bg-primary/[0.04]'
                    )}
                  >
                    <div className="mt-0.5">{getCategoryIcon(n.category, n.severity)}</div>
                    <div className="flex-1 min-w-0 pr-6">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className={cn('text-xs font-semibold truncate', !n.is_read ? 'text-foreground' : 'text-muted-foreground')}>
                          {n.title}
                        </p>
                        <span className="text-[10px] text-muted-foreground/60 whitespace-nowrap">
                          {new Date(n.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5 leading-relaxed">
                        {n.message}
                      </p>
                      {n.action_url && (
                        <Link
                          to={n.action_url}
                          onClick={() => {
                            if (!n.is_read) markAsRead(n.id)
                            setIsOpen(false)
                          }}
                          className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline mt-1.5"
                        >
                          View details
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                      )}
                    </div>
                    {/* Action buttons on hover */}
                    <div className="absolute right-2 top-3 flex items-center opacity-0 group-hover:opacity-100 transition-opacity">
                      {!n.is_read && (
                        <button
                          onClick={() => markAsRead(n.id)}
                          title="Mark as read"
                          className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-muted"
                        >
                          <CheckCheck className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        onClick={() => dismissNotification(n.id)}
                        title="Dismiss"
                        className="p-1 text-muted-foreground hover:text-destructive rounded hover:bg-muted"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Popover Footer */}
            <div className="p-2.5 border-t border-border bg-card/40 text-center">
              <Link
                to="/settings/notifications"
                onClick={() => setIsOpen(false)}
                className="text-xs font-medium text-primary hover:underline block py-1"
              >
                View all notifications in Settings →
              </Link>
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
