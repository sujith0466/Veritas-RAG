import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  Briefcase,
  Users,
  CreditCard,
  Activity,
  ShieldAlert,
  Menu,
  X,
  ArrowLeft,
  ChevronRight,
  ShieldCheck,
  Building2,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { cn } from '@/utils/cn'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/common/Button'

interface AdminNavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  description: string
  badge?: string
}

const adminNav: AdminNavItem[] = [
  {
    name: 'Workspace Settings',
    href: '/admin/workspace',
    icon: Briefcase,
    description: 'Identity, policies, and data exports',
  },
  {
    name: 'Members & Access',
    href: '/admin/members',
    icon: Users,
    description: 'Team seats, invitations, and roles',
  },
  {
    name: 'Resource & Governance',
    href: '/admin/quota',
    icon: CreditCard,
    description: 'Inference limits and token policies',
  },
  {
    name: 'Audit Ledger',
    href: '/admin/audit',
    icon: Activity,
    description: 'Security and administrative audit trail',
  },
]

export function AdminLayout() {
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const shouldReduceMotion = useReducedMotion()
  const [mobileOpen, setMobileOpen] = useState(false)

  const isPlatformAdmin = String(user?.role || '').trim().toLowerCase() === 'platform_admin'
  const userRole = String(user?.role || 'MEMBER').trim().toUpperCase()
  const workspaceName = user?.workspace_name || 'Current Workspace'

  const navItems = [...adminNav]
  if (isPlatformAdmin) {
    navItems.push({
      name: 'Platform Admin',
      href: '/admin/platform',
      icon: ShieldAlert,
      description: 'Cross-workspace global infrastructure',
      badge: 'SYSTEM',
    })
  }

  const renderNavLinks = (onItemClick?: () => void) => (
    <nav className="space-y-1.5" aria-label="Admin Navigation">
      <div className="px-3 pb-2 text-2xs font-mono font-semibold uppercase tracking-wider text-muted-foreground/70">
        Control Plane
      </div>
      {navItems.map((item) => {
        const isActive = location.pathname.startsWith(item.href)
        const Icon = item.icon
        return (
          <Link
            key={item.name}
            to={item.href}
            onClick={onItemClick}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'group relative flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1',
              isActive
                ? 'bg-primary/10 text-primary font-semibold shadow-xs'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
            )}
          >
            {isActive && !shouldReduceMotion && (
              <motion.div
                layoutId="admin-active-pill"
                className="absolute left-0 top-1.5 bottom-1.5 w-1 bg-primary rounded-r"
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              />
            )}
            <div className="flex items-center gap-3">
              <div
                className={cn(
                  'p-1.5 rounded-md transition-colors',
                  isActive ? 'bg-primary/15 text-primary' : 'bg-muted/50 text-muted-foreground group-hover:text-foreground'
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="flex flex-col text-left">
                <span className="leading-tight">{item.name}</span>
              </div>
            </div>
            {item.badge ? (
              <span className="text-2xs font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20">
                {item.badge}
              </span>
            ) : isActive ? (
              <ChevronRight className="h-3.5 w-3.5 text-primary/70" />
            ) : null}
          </Link>
        )
      })}
    </nav>
  )

  return (
    <div className="flex flex-col h-full bg-background text-foreground">
      {/* Mobile Top Navigation Bar */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-card/60 backdrop-blur-md sticky top-0 z-20">
        <div className="flex items-center gap-2.5">
          <Link
            to="/dashboard"
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Return to Dashboard"
            aria-label="Return to Dashboard"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span className="font-semibold text-sm">Admin Console</span>
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? 'Close navigation drawer' : 'Open navigation drawer'}
          className="p-2 h-8 w-8"
        >
          {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>

      {/* Mobile Navigation Drawer Sheet */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={() => setMobileOpen(false)}
              className="md:hidden fixed inset-0 z-30 bg-background/80 backdrop-blur-sm"
              aria-hidden="true"
            />
            <motion.div
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              className="md:hidden fixed inset-y-0 left-0 z-40 w-72 bg-card border-r border-border p-5 flex flex-col shadow-2xl"
            >
              <div className="flex items-center justify-between pb-4 border-b border-border/60 mb-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <span className="font-bold text-base">Administration</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setMobileOpen(false)}
                  className="h-8 w-8 p-0"
                  aria-label="Close menu"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              {/* Workspace Badge Mobile */}
              <div className="p-3 mb-4 rounded-lg bg-muted/40 border border-border/50 space-y-1">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Building2 className="h-3.5 w-3.5" />
                  <span className="font-medium truncate">{workspaceName}</span>
                </div>
                <div className="flex items-center justify-between pt-1 text-2xs">
                  <span className="text-muted-foreground font-mono">Role</span>
                  <span className="font-mono font-semibold text-primary">{userRole}</span>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto">
                {renderNavLinks(() => setMobileOpen(false))}
              </div>

              <div className="pt-4 border-t border-border/60">
                <Link
                  to="/dashboard"
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors p-2"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  <span>Exit to Main Dashboard</span>
                </Link>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Main Layout Container */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop Persistent Sidebar */}
        <aside className="w-68 flex-shrink-0 border-r border-border/70 bg-card/30 overflow-y-auto hidden md:flex flex-col justify-between">
          <div className="p-4 space-y-5">
            {/* Context Header Card */}
            <div className="p-3.5 rounded-lg bg-card border border-border/80 shadow-xs space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground truncate">
                  <Building2 className="h-3.5 w-3.5 text-primary flex-shrink-0" />
                  <span className="truncate">{workspaceName}</span>
                </div>
                <span className="text-2xs font-mono font-semibold px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                  {userRole}
                </span>
              </div>
              <p className="text-2xs text-muted-foreground leading-tight">
                Authoritative Workspace Control Plane
              </p>
            </div>

            {/* Navigation links */}
            {renderNavLinks()}
          </div>

          {/* Sidebar Footer Link */}
          <div className="p-4 border-t border-border/50">
            <Link
              to="/dashboard"
              className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back to Workspace</span>
            </Link>
          </div>
        </aside>

        {/* Content Viewport */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 lg:p-10">
          <div className="max-w-6xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
