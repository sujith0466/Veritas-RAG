import { useState, useEffect, useRef } from 'react'
import { Bell } from 'lucide-react'
import { Button } from './Button'
import { Card } from './Card'
import { useAuthStore } from '@/stores/authStore'
import { useToast } from '@/hooks/useToast'
import { cn } from '@/utils/cn'

interface Notification {
  id: string
  type: string
  payload: any
  timestamp: string
  read: boolean
}

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  
  const token = useAuthStore(s => s.token)
  const { toast } = useToast()

  useEffect(() => {
    if (!token) return

    // Secure WebSocket connection using token in query
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/v1/notifications/ws?token=${token}`
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const newNotif: Notification = {
          id: crypto.randomUUID(),
          type: data.type,
          payload: data.payload,
          timestamp: data.timestamp || new Date().toISOString(),
          read: false
        }
        
        setNotifications(prev => [newNotif, ...prev].slice(0, 50)) // Keep last 50
        setHasUnread(true)
        
        // Optionally toast for high priority events
        if (data.type.includes('COMPLETED') || data.type.includes('FAILED') || data.type.includes('READY')) {
            toast({
                title: 'New Event',
                message: data.type,
                type: data.type.includes('FAILED') ? 'error' : 'success'
            })
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message', err)
      }
    }

    return () => {
      ws.close()
    }
  }, [token])
  
  const toggleOpen = () => {
    setIsOpen(!isOpen)
    if (!isOpen) {
      setHasUnread(false)
      // Mark all as read when opening
      setNotifications(prev => prev.map(n => ({ ...n, read: true })))
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
        {hasUnread && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-background transition-transform group-hover:scale-110 motion-reduce:group-hover:scale-100" />
        )}
      </Button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)}></div>
          <Card className="absolute right-0 mt-2 w-80 max-h-[400px] overflow-y-auto z-50 shadow-lg animate-in fade-in slide-in-from-top-2">
            <div className="p-4 border-b border-border sticky top-0 bg-background/95 backdrop-blur z-10 flex justify-between items-center">
              <h3 className="font-semibold text-sm">Notifications</h3>
              <span className="text-xs text-muted-foreground">{notifications.length} recent</span>
            </div>
            <div className="divide-y divide-border">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground text-sm">
                  No notifications yet.
                </div>
              ) : (
                notifications.map(n => (
                  <div key={n.id} className={cn("p-4 text-sm transition-colors hover:bg-muted/50", !n.read && "bg-primary/5")}>
                    <div className="font-medium text-foreground mb-1">{n.type}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {n.payload?.document_id || n.payload?.file_name || 'System Event'}
                    </div>
                    <div className="text-[10px] text-muted-foreground mt-2 opacity-70">
                      {new Date(n.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  )
}
