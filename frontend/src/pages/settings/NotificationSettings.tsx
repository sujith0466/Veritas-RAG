import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell,
  CheckCheck,
  ExternalLink,
  ShieldAlert,
  FileText,
  Settings,
  Info,
  AlertTriangle,
  AlertCircle,
  Trash2,
  SlidersHorizontal,
  Inbox,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react'
import { Card, Button, SectionHeader } from '@/components/common'
import { useToast } from '@/hooks/useToast'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { useInAppNotificationStore } from '@/stores/inAppNotificationStore'
import { cn } from '@/utils/cn'

export function NotificationSettings() {
  const { toast } = useToast()
  const user = useAuthStore((s) => s.user)
  const setAuth = useAuthStore((s) => s.setAuth)
  const token = useAuthStore((s) => s.token)

  // Tabs: 'inbox' (Notification Center / Activity) vs 'preferences' (Delivery Preferences)
  const [activeTab, setActiveTab] = useState<'inbox' | 'preferences'>('inbox')

  // Preferences State
  const [loadingPrefs, setLoadingPrefs] = useState(true)
  const [savingPrefs, setSavingPrefs] = useState(false)
  const [preferences, setPreferences] = useState({
    email_alerts: true,
    security_alerts: true,
    weekly_reports: false,
  })

  // Inbox State & Filtering
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL')
  const [unreadFilter, setUnreadFilter] = useState<boolean>(false)
  const [searchQuery, setSearchQuery] = useState<string>('')

  const {
    notifications,
    unreadCount,
    loading: loadingNotifications,
    fetchNotifications,
    markAsRead,
    markAllAsRead,
    dismissNotification,
  } = useInAppNotificationStore()

  useEffect(() => {
    loadPreferences()
  }, [])

  useEffect(() => {
    if (activeTab === 'inbox' && token) {
      loadInbox()
    }
  }, [activeTab, selectedCategory, unreadFilter, token])

  const loadPreferences = async () => {
    try {
      const { data } = await userService.getProfile()
      const prefs = data.preferences?.notifications || {}
      setPreferences({
        email_alerts: prefs.email_alerts ?? true,
        security_alerts: prefs.security_alerts ?? true,
        weekly_reports: prefs.weekly_reports ?? false,
      })
    } catch {
      toast({ title: 'Error', message: 'Failed to load notification preferences', type: 'error' })
    } finally {
      setLoadingPrefs(false)
    }
  }

  const loadInbox = () => {
    const params: { category?: string; unread_only?: boolean; page?: number; page_size?: number } = {
      page: 1,
      page_size: 50,
      unread_only: unreadFilter,
    }
    if (selectedCategory !== 'ALL') {
      params.category = selectedCategory
    }
    fetchNotifications(params)
  }

  const handleTogglePref = (key: keyof typeof preferences) => {
    setPreferences((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSavePreferences = async () => {
    setSavingPrefs(true)
    try {
      const { data } = await userService.updatePreferences({
        preferences: {
          ...user?.preferences,
          notifications: preferences,
        },
      })

      if (user && token) {
        setAuth({ ...user, ...data }, token)
      }

      toast({ title: 'Success', message: 'Notification preferences updated successfully', type: 'success' })
    } catch {
      toast({ title: 'Error', message: 'Failed to update preferences', type: 'error' })
    } finally {
      setSavingPrefs(false)
    }
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

  const filteredNotifications = notifications.filter((n) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return n.title.toLowerCase().includes(q) || n.message.toLowerCase().includes(q)
  })

  const renderSwitch = (checked: boolean, onChange: () => void) => (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 ${
        checked ? 'bg-primary' : 'bg-muted'
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </button>
  )

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <SectionHeader
          title="Notification Center"
          description="Manage your in-app activity feed, alerts, and communication preferences."
        />
        {/* Navigation Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-muted/60 border border-border/60 rounded-xl self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setActiveTab('inbox')}
            className={cn(
              'flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200',
              activeTab === 'inbox'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <Inbox className="w-3.5 h-3.5" />
            <span>Inbox & Activity</span>
            {unreadCount > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-primary/20 text-primary px-1 text-[10px] font-bold">
                {unreadCount}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('preferences')}
            className={cn(
              'flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200',
              activeTab === 'preferences'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Preferences</span>
          </button>
        </div>
      </div>

      {activeTab === 'inbox' ? (
        <div className="space-y-4">
          {/* Controls Bar */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 bg-card/60 border border-border/80 rounded-xl">
            <div className="flex flex-wrap items-center gap-2">
              {/* Category Filter Pills */}
              {['ALL', 'SECURITY', 'DOCUMENT', 'WORKSPACE', 'SYSTEM'].map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                    selectedCategory === cat
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted'
                  )}
                >
                  {cat === 'ALL' ? 'All Events' : cat}
                </button>
              ))}

              <div className="h-4 w-px bg-border/60 mx-1 hidden sm:block" />

              {/* Unread Only Toggle */}
              <button
                onClick={() => setUnreadFilter(!unreadFilter)}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                  unreadFilter
                    ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30'
                    : 'bg-muted/60 text-muted-foreground hover:text-foreground'
                )}
              >
                Unread only
              </button>
            </div>

            <div className="flex items-center gap-2">
              <div className="relative flex-1 md:w-56">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Filter notifications..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1 text-xs rounded-lg border border-border/80 bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <Button
                variant="outline"
                size="sm"
                onClick={loadInbox}
                className="h-7 px-2 text-xs"
                title="Refresh"
              >
                <RefreshCw className={cn('w-3.5 h-3.5', loadingNotifications && 'animate-spin')} />
              </Button>

              {unreadCount > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => markAllAsRead()}
                  className="h-7 px-2.5 text-xs font-medium"
                >
                  <CheckCheck className="w-3.5 h-3.5 mr-1" />
                  Mark all read
                </Button>
              )}
            </div>
          </div>

          {/* Activity Feed Table/Card */}
          <Card className="p-0 overflow-hidden divide-y divide-border/60">
            {loadingNotifications && notifications.length === 0 ? (
              <div className="flex justify-center items-center py-20">
                <Loader2 className="animate-spin text-primary h-7 w-7" />
              </div>
            ) : filteredNotifications.length === 0 ? (
              <div className="p-16 text-center text-muted-foreground text-sm flex flex-col items-center justify-center gap-2">
                <Inbox className="w-10 h-10 text-muted-foreground/30 stroke-[1.5]" />
                <p className="text-sm font-semibold text-foreground">No notifications found</p>
                <p className="text-xs text-muted-foreground max-w-sm">
                  {searchQuery || unreadFilter || selectedCategory !== 'ALL'
                    ? 'No notifications match the current filters. Try resetting your query.'
                    : "You're completely up to date with workspace activity."}
                </p>
              </div>
            ) : (
              filteredNotifications.map((n) => (
                <div
                  key={n.id}
                  className={cn(
                    'p-4 text-sm transition-colors hover:bg-muted/40 flex items-start justify-between gap-4 group',
                    !n.is_read && 'bg-primary/[0.03]'
                  )}
                >
                  <div className="flex items-start gap-3.5 min-w-0 flex-1">
                    <div className="mt-0.5 p-1.5 rounded-lg bg-muted/60 border border-border/60">
                      {getCategoryIcon(n.category, n.severity)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="font-semibold text-xs text-foreground">{n.title}</span>
                        <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.2 rounded bg-muted text-muted-foreground">
                          {n.category}
                        </span>
                        {!n.is_read && (
                          <span className="w-2 h-2 rounded-full bg-primary" title="Unread" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground leading-relaxed break-words">{n.message}</p>
                      <div className="flex items-center gap-4 mt-2">
                        <span className="text-[11px] text-muted-foreground/60">
                          {new Date(n.created_at).toLocaleString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {n.action_url && (
                          <Link
                            to={n.action_url}
                            onClick={() => {
                              if (!n.is_read) markAsRead(n.id)
                            }}
                            className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                          >
                            Go to resource
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100 transition-opacity self-start mt-1">
                    {!n.is_read && (
                      <button
                        onClick={() => markAsRead(n.id)}
                        title="Mark as read"
                        className="p-1.5 text-muted-foreground hover:text-foreground rounded-lg hover:bg-muted/80 transition-colors"
                      >
                        <CheckCheck className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      onClick={() => dismissNotification(n.id)}
                      title="Dismiss"
                      className="p-1.5 text-muted-foreground hover:text-destructive rounded-lg hover:bg-muted/80 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </Card>
        </div>
      ) : (
        /* Preferences Tab */
        <div className="space-y-6">
          {loadingPrefs ? (
            <div className="flex justify-center items-center h-48">
              <Loader2 className="animate-spin text-primary h-8 w-8" />
            </div>
          ) : (
            <>
              <Card className="p-0 overflow-hidden divide-y divide-border/50">
                <div className="flex items-center justify-between p-6">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-primary/10 rounded-lg text-primary mt-1">
                      <Bell className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">General Document & Pipeline Alerts</h3>
                      <p className="text-sm text-muted-foreground mt-1 max-w-md">
                        Receive notifications when documents finish indexing, chunking, embedding, or report ingestion errors.
                      </p>
                    </div>
                  </div>
                  {renderSwitch(preferences.email_alerts, () => handleTogglePref('email_alerts'))}
                </div>

                <div className="flex items-center justify-between p-6">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-danger/10 rounded-lg text-danger mt-1">
                      <ShieldAlert className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground">Security & Reliability Alerts</h3>
                      <p className="text-sm text-muted-foreground mt-1 max-w-md">
                        Get immediate notifications when passwords change, active sessions rotate, or security guardrails trigger.
                      </p>
                    </div>
                  </div>
                  {renderSwitch(preferences.security_alerts, () => handleTogglePref('security_alerts'))}
                </div>

                <div className="flex items-center justify-between p-6 opacity-75 bg-muted/20">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-muted rounded-lg text-muted-foreground mt-1">
                      <FileText className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-foreground">Weekly Digest & Usage Summary</h3>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider bg-muted text-muted-foreground border border-border/60">
                          Coming Soon
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mt-1 max-w-md">
                        Automated weekly email reports summarizing workspace queries, groundedness scores, and token usage. Scheduled delivery is currently in development.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={false}
                    disabled
                    aria-label="Weekly digest is coming soon"
                    className="relative inline-flex h-6 w-11 shrink-0 cursor-not-allowed rounded-full border-2 border-transparent bg-muted/60 opacity-60 transition-colors"
                  >
                    <span
                      aria-hidden="true"
                      className="pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 translate-x-0 transition duration-200"
                    />
                  </button>
                </div>
              </Card>

              <div className="flex justify-end">
                <Button onClick={handleSavePreferences} isLoading={savingPrefs}>
                  Save Preferences
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
