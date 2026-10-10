import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  User, Shield, Bell, Brain,
  Briefcase, Lock, Webhook
} from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { cn } from '@/utils/cn'

const settingsNav = [
  { name: 'Profile', href: '/settings/profile', icon: User },
  { name: 'Security', href: '/settings/security', icon: Shield },
  { name: 'Notifications', href: '/settings/notifications', icon: Bell },
  { name: 'AI Preferences', href: '/settings/ai', icon: Brain },
  { name: 'Workspace', href: '/settings/workspace', icon: Briefcase },
  { name: 'Webhooks', href: '/settings/webhooks', icon: Webhook },
  { name: 'Privacy', href: '/settings/privacy', icon: Lock },
]

export function SettingsLayout() {
  const location = useLocation()

  return (
    <div className="flex flex-col h-full bg-background">
      <PageHeader
        title="Settings"
        description="Manage your account, preferences, and workspace configuration."
      />

      {/* Mobile Horizontal Navigation Tabs (< 768px) */}
      <div className="md:hidden border-b border-border bg-card/40 px-4 py-2 overflow-x-auto scrollbar-none flex items-center gap-1.5 flex-nowrap shrink-0">
        {settingsNav.map((item) => {
          const isActive = location.pathname.startsWith(item.href)
          const Icon = item.icon
          return (
            <Link
              key={item.name}
              to={item.href}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors shrink-0',
                isActive
                  ? 'bg-primary text-primary-foreground shadow-xs'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Sidebar (>= 768px) */}
        <aside className="w-64 flex-shrink-0 border-r border-border overflow-y-auto hidden md:block">
          <nav className="p-4 space-y-1">
            {settingsNav.map((item) => {
              const isActive = location.pathname.startsWith(item.href)
              const Icon = item.icon
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary font-semibold'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.name}
                </Link>
              )
            })}
          </nav>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
          <div className="max-w-4xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
