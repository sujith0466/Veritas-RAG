import { Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Shield,
  Settings,
  ChevronLeft,
  Menu,
  Activity,
  Users,
  FileText,
  Layers,
  Cpu,
  Database,
  BarChart3,
  Brain,
  Terminal,
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { cn } from '@/utils/cn'
import { sidebarVariants, sidebarLabelVariants } from '@/motion'
import { Badge } from '../common/Badge'

export function Sidebar() {
  const location = useLocation()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const user = useAuthStore((s) => s.user)

  const navigation = [
    {
      group: 'Overview',
      items: [
        { name: 'Executive Overview', href: '/dashboard', icon: LayoutDashboard },
        { name: 'Knowledge Intelligence', href: '/knowledge-intelligence', icon: Brain },
        { name: 'AI Reliability & Analytics', href: '/analytics', icon: BarChart3 },
        { name: 'Investigation Console', href: '/investigation', icon: Terminal },
        { name: 'Documents', href: '/documents', icon: FileText },
        { name: 'Knowledge Chunks', href: '/chunks', icon: Layers },
        { name: 'Vector Embeddings', href: '/embeddings', icon: Cpu },
        { name: 'Vector Storage', href: '/vectors', icon: Database },
        { name: 'System Health', href: '/admin/health', icon: Activity, adminOnly: true },
      ],
    },
    {
      group: 'Settings',
      items: [
        { name: 'Access Control', href: '/admin/users', icon: Users, adminOnly: true },
        { name: 'Preferences', href: '/settings', icon: Settings },
      ],
    },
  ]

  return (
    <motion.aside
      variants={sidebarVariants}
      initial={sidebarCollapsed ? 'collapsed' : 'expanded'}
      animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
      className="relative z-40 hidden h-screen flex-col border-r border-border bg-surface/50 backdrop-blur-xl md:flex shrink-0"
    >
      {/* Brand Header */}
      <div className="flex h-14 items-center justify-between px-4 border-b border-border/50">
        <div className="flex items-center gap-3 overflow-hidden">
          <Shield className="h-6 w-6 shrink-0 text-primary" />
          <AnimatePresence initial={false}>
            {!sidebarCollapsed && (
              <motion.span
                variants={sidebarLabelVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="font-bold text-foreground whitespace-nowrap"
              >
                RAGuard AI
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Toggle Button */}
      <button
        onClick={toggleSidebar}
        className="absolute -right-3.5 top-16 z-50 flex h-7 w-7 items-center justify-center rounded-full border border-border bg-surface text-muted-foreground shadow-sm hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        {sidebarCollapsed ? <Menu className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-4 scrollbar-none">
        <nav className="space-y-6 px-2">
          {navigation.map((section, i) => {
            const items = section.items.filter(
              (item) => !item.adminOnly || user?.role === 'admin'
            )
            
            if (items.length === 0) return null

            return (
              <div key={i}>
                {!sidebarCollapsed && (
                  <motion.div
                    variants={sidebarLabelVariants}
                    initial="collapsed"
                    animate="expanded"
                    exit="collapsed"
                    className="mb-2 px-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase"
                  >
                    {section.group}
                  </motion.div>
                )}
                <div className="space-y-1">
                  {items.map((item) => {
                    const isActive = location.pathname.startsWith(item.href)
                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        className={cn(
                          'relative flex items-center gap-3 rounded-md px-2 py-2 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary',
                          isActive
                            ? 'text-primary'
                            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                          sidebarCollapsed && 'justify-center',
                        )}
                        title={sidebarCollapsed ? item.name : undefined}
                      >
                        {isActive && (
                          <motion.div
                            layoutId="sidebar-active-indicator"
                            className="absolute inset-0 rounded-md bg-primary/10"
                            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                          />
                        )}
                        <item.icon
                          className={cn('h-5 w-5 shrink-0 z-10', isActive && 'text-primary')}
                        />
                        <AnimatePresence initial={false}>
                          {!sidebarCollapsed && (
                            <motion.span
                              variants={sidebarLabelVariants}
                              initial="collapsed"
                              animate="expanded"
                              exit="collapsed"
                              className="z-10 font-medium whitespace-nowrap overflow-hidden"
                            >
                              {item.name}
                            </motion.span>
                          )}
                        </AnimatePresence>
                      </Link>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </nav>
      </div>

      {/* Footer / User stub */}
      <div className="border-t border-border/50 p-4">
        <div className={cn("flex items-center gap-3", sidebarCollapsed && "justify-center")}>
          <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-primary flex items-center justify-center text-xs font-bold text-white shadow-sm">
            {user?.email?.charAt(0).toUpperCase() || 'U'}
          </div>
          {!sidebarCollapsed && (
            <motion.div
              variants={sidebarLabelVariants}
              initial="collapsed"
              animate="expanded"
              exit="collapsed"
              className="flex flex-col overflow-hidden"
            >
              <span className="truncate text-sm font-medium">{user?.email}</span>
              <Badge variant="subtle" className="w-fit text-[10px] h-4 mt-0.5 px-1.5 uppercase">
                {user?.role || 'VIEWER'}
              </Badge>
            </motion.div>
          )}
        </div>
      </div>
    </motion.aside>
  )
}
