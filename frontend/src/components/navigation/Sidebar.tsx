import { Link, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Shield,
  ChevronLeft,
  ChevronRight,
  Activity,
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

interface NavItem {
  name: string
  href: string
  icon: React.ElementType
  adminOnly?: boolean
  badge?: string
  description?: string
}

interface NavGroup {
  group: string
  items: NavItem[]
}

const navigation: NavGroup[] = [
  {
    group: 'Intelligence',
    items: [
      {
        name: 'Executive Overview',
        href: '/dashboard',
        icon: LayoutDashboard,
        description: 'KPIs and system status',
      },
      {
        name: 'Knowledge Intelligence',
        href: '/knowledge-intelligence',
        icon: Brain,
        description: 'Knowledge health analytics',
      },
      {
        name: 'AI Reliability',
        href: '/analytics',
        icon: BarChart3,
        description: 'Reliability scoring',
      },
    ],
  },
  {
    group: 'RAG Pipeline',
    items: [
      {
        name: 'Documents',
        href: '/documents',
        icon: FileText,
        description: 'Document ingestion',
      },
      {
        name: 'Knowledge Chunks',
        href: '/chunks',
        icon: Layers,
        description: 'Chunking & segmentation',
      },
      {
        name: 'Vector Embeddings',
        href: '/embeddings',
        icon: Cpu,
        description: 'Embedding pipeline',
      },
      {
        name: 'Vector Storage',
        href: '/vectors',
        icon: Database,
        description: 'Qdrant vector store',
      },
    ],
  },
  {
    group: 'Operations',
    items: [
      {
        name: 'Investigation',
        href: '/investigation',
        icon: Terminal,
        adminOnly: true,
        description: 'System investigation',
      },
      {
        name: 'System Health',
        href: '/admin/health',
        icon: Activity,
        adminOnly: true,
        description: 'Infrastructure health',
      },
    ],
  },
]

export function Sidebar() {
  const location = useLocation()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const user = useAuthStore((s) => s.user)

  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : 'U'

  return (
    <motion.aside
      variants={sidebarVariants}
      initial={sidebarCollapsed ? 'collapsed' : 'expanded'}
      animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
      className="relative z-40 hidden h-screen flex-col border-r border-border/60 bg-surface/40 backdrop-blur-xl md:flex shrink-0"
    >
      {/* Brand Header */}
      <div className="flex h-14 items-center justify-between px-4 border-b border-border/50">
        <div className="flex items-center gap-2.5 overflow-hidden min-w-0">
          {/* Logo mark */}
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 ring-1 ring-primary/20">
            <Shield className="h-4 w-4 text-primary" />
          </div>
          <AnimatePresence initial={false}>
            {!sidebarCollapsed && (
              <motion.div
                variants={sidebarLabelVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden min-w-0"
              >
                <div className="font-bold text-sm text-foreground whitespace-nowrap tracking-tight">
                  RAGuard AI
                </div>
                <div className="text-[10px] text-muted-foreground whitespace-nowrap font-medium tracking-wide uppercase">
                  RAG Platform
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Collapse Toggle Button */}
      <button
        onClick={toggleSidebar}
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="absolute -right-3 top-[3.75rem] z-50 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-surface text-muted-foreground shadow-sm hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors"
      >
        {sidebarCollapsed
          ? <ChevronRight className="h-3.5 w-3.5" />
          : <ChevronLeft className="h-3.5 w-3.5" />
        }
      </button>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3 scrollbar-none">
        <nav className="px-2 space-y-5">
          {navigation.map((section, i) => {
            const items = section.items.filter(
              (item) => !item.adminOnly || user?.role === 'admin'
            )

            if (items.length === 0) return null

            return (
              <div key={i}>
                {/* Group Label */}
                <AnimatePresence initial={false}>
                  {!sidebarCollapsed && (
                    <motion.div
                      variants={sidebarLabelVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                      className="mb-1.5 px-2 text-[10px] font-semibold tracking-widest text-muted-foreground/70 uppercase"
                    >
                      {section.group}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Nav Items */}
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const isActive = location.pathname === item.href ||
                      (item.href !== '/dashboard' && location.pathname.startsWith(item.href))

                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        title={sidebarCollapsed ? item.name : undefined}
                        className={cn(
                          'group relative flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary',
                          isActive
                            ? 'text-primary'
                            : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
                          sidebarCollapsed && 'justify-center px-2'
                        )}
                      >
                        {/* Active background */}
                        {isActive && (
                          <motion.div
                            layoutId="sidebar-active-bg"
                            className="absolute inset-0 rounded-lg bg-primary/8"
                            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                          />
                        )}

                        {/* Active left border pill */}
                        {isActive && !sidebarCollapsed && (
                          <motion.div
                            layoutId="sidebar-active-pill"
                            className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-primary"
                            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                          />
                        )}

                        {/* Icon */}
                        <item.icon
                          className={cn(
                            'h-4 w-4 shrink-0 z-10 transition-colors',
                            isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground'
                          )}
                        />

                        {/* Label */}
                        <AnimatePresence initial={false}>
                          {!sidebarCollapsed && (
                            <motion.span
                              variants={sidebarLabelVariants}
                              initial="collapsed"
                              animate="expanded"
                              exit="collapsed"
                              className="z-10 font-medium whitespace-nowrap overflow-hidden text-sm"
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

      {/* Separator */}
      <div className="h-px bg-border/50 mx-3" />

      {/* User Footer */}
      <div className="p-3">
        <div
          className={cn(
            'flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-muted/60 transition-colors cursor-default',
            sidebarCollapsed && 'justify-center'
          )}
        >
          {/* Avatar */}
          <div className="h-7 w-7 shrink-0 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-[11px] font-bold text-white shadow-sm ring-1 ring-white/10">
            {initials}
          </div>

          <AnimatePresence initial={false}>
            {!sidebarCollapsed && (
              <motion.div
                variants={sidebarLabelVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="flex flex-col overflow-hidden min-w-0"
              >
                <span className="truncate text-xs font-medium text-foreground">
                  {user?.full_name || user?.email?.split('@')[0] || 'User'}
                </span>
                <Badge
                  variant="subtle"
                  className="w-fit text-[9px] h-3.5 mt-0.5 px-1.5 uppercase tracking-wider"
                >
                  {user?.role || 'viewer'}
                </Badge>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.aside>
  )
}
