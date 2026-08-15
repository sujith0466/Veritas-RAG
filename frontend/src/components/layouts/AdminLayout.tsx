import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  Briefcase, Users, CreditCard, Activity, ShieldAlert
} from 'lucide-react'
import { PageHeader } from '@/components/common/PageHeader'
import { cn } from '@/utils/cn'
import { useAuthStore } from '@/stores/authStore'

const adminNav = [
  { name: 'Workspace Settings', href: '/admin/workspace', icon: Briefcase },
  { name: 'Members & Access', href: '/admin/members', icon: Users },
  { name: 'Quota & Billing', href: '/admin/quota', icon: CreditCard },
  { name: 'Audit Logs', href: '/admin/audit', icon: Activity },
]

export function AdminLayout() {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)

  // Determine if user has platform admin role
  const isPlatformAdmin = user?.role === 'platform_admin'
  const navItems = [...adminNav]
  if (isPlatformAdmin) {
    navItems.push({ name: 'Platform Admin', href: '/admin/platform', icon: ShieldAlert })
  }

  return (
    <div className="flex flex-col h-full bg-background">
      <PageHeader
        title="Administration"
        description="Manage workspace configuration, members, billing, and security logs."
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0 border-r border-border overflow-y-auto hidden md:block">
          <nav className="p-4 space-y-1">
            {navItems.map((item) => {
              const isActive = location.pathname.startsWith(item.href)
              const Icon = item.icon
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
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
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
