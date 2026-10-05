import { useEffect, useState, useMemo, useRef } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Shield,
  ChevronLeft,
  ChevronRight,
  Activity,
  FileText,
  Workflow,
  BarChart3,
  Brain,
  MessageSquare,
  Plus,

  Pencil,
  Trash2,
  Pin,
  Archive,
  ArchiveRestore,
  MoreHorizontal
} from 'lucide-react'
import { isToday, isYesterday, differenceInCalendarDays, parseISO } from 'date-fns'

import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { useChatStore, ChatSession } from '@/stores/chatStore'
import { cn } from '@/utils/cn'
import { sidebarVariants, sidebarLabelVariants } from '@/motion'
import { Badge } from '../common/Badge'

interface NavItem {
  name: string
  href: string
  icon: React.ElementType
  adminOnly?: boolean
  matchPrefix?: boolean
}

interface NavGroup {
  group?: string
  items: NavItem[]
}

const navigation: NavGroup[] = [
  {
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Workspace Analytics', href: '/workspace-analytics', icon: Activity, adminOnly: true },
      { name: 'Knowledge', href: '/knowledge', icon: Brain, adminOnly: true },
      { name: 'Documents', href: '/documents', icon: FileText, adminOnly: true },
      { name: 'Knowledge Processing', href: '/knowledge-processing', icon: Workflow, adminOnly: true },
      { name: 'AI Reliability & Diag', href: '/reliability', icon: BarChart3, adminOnly: true, matchPrefix: true },
      { name: 'Knowledge Health', href: '/knowledge-health', icon: Activity, adminOnly: true, matchPrefix: true },
      { name: 'Admin Portal', href: '/admin', icon: Shield, adminOnly: true, matchPrefix: true },
    ],
  },
]

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const user = useAuthStore((s) => s.user)

  const { sessions, fetchSessions, updateSession, deleteSession, archiveSession, restoreSession } = useChatStore()

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const handleNewChat = () => {
    navigate('/chat', { state: { autoFocus: Date.now() } })
  }

  const groupedSessions = useMemo(() => {
    const groups = {
      pinned: [] as ChatSession[],
      today: [] as ChatSession[],
      yesterday: [] as ChatSession[],
      previous7Days: [] as ChatSession[],
      older: [] as ChatSession[]
    }

    sessions.forEach(session => {
      if (session.pinned) {
        groups.pinned.push(session)
        return
      }

      const date = parseISO(session.updated_at)
      const diff = differenceInCalendarDays(new Date(), date)
      if (diff <= 0 || isToday(date)) groups.today.push(session)
      else if (diff === 1 || isYesterday(date)) groups.yesterday.push(session)
      else if (diff <= 7) groups.previous7Days.push(session)
      else groups.older.push(session)
    })

    return groups
  }, [sessions])

  const initials = user?.email ? user.email.slice(0, 2).toUpperCase() : 'U'

  return (
    <motion.aside
      variants={sidebarVariants}
      initial={sidebarCollapsed ? 'collapsed' : 'expanded'}
      animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
      className="relative z-40 hidden h-screen flex-col border-r border-border/60 bg-surface/40 backdrop-blur-xl md:flex shrink-0"
    >
      <div className="flex h-14 items-center justify-between px-4 border-b border-border/50">
        <div className="flex items-center gap-2.5 overflow-hidden min-w-0">
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
                  Veritas RAG
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      <button
        onClick={toggleSidebar}
        className="absolute -right-3 top-[3.75rem] z-50 flex h-6 w-6 items-center justify-center rounded-full border border-border bg-surface text-muted-foreground shadow-sm hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors"
      >
        {sidebarCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
      </button>

      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3 scrollbar-none flex flex-col">
        {/* Main Navigation */}
        <nav className="px-2 space-y-1 pb-4">
          {navigation.map((section, i) => {
            const roleStr = String(user?.role || '').trim().toLowerCase()
            const items = section.items.filter(item => !item.adminOnly || ['admin', 'owner', 'platform_admin'].includes(roleStr))
            if (items.length === 0) return null

            return (
              <div key={i} className="mb-2">
                {i > 0 && <div className="h-px bg-border/40 mx-2 my-2" />}
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const isActive = item.matchPrefix
                      ? location.pathname.startsWith(item.href)
                      : location.pathname === item.href

                    return (
                      <Link
                        key={item.name}
                        to={item.href}
                        title={sidebarCollapsed ? item.name : undefined}
                        className={cn(
                          'group relative flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary',
                          isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
                          sidebarCollapsed && 'justify-center px-2'
                        )}
                      >
                        {isActive && (
                          <motion.div
                            layoutId="sidebar-active-bg"
                            className="absolute inset-0 rounded-lg bg-primary/8"
                            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                          />
                        )}
                        <item.icon className={cn('h-4 w-4 shrink-0 z-10 transition-colors', isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground')} />
                        <AnimatePresence initial={false}>
                          {!sidebarCollapsed && (
                            <motion.span variants={sidebarLabelVariants} initial="collapsed" animate="expanded" exit="collapsed" className="z-10 font-medium whitespace-nowrap overflow-hidden text-sm">
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

        {/* Chat History Section */}
        <div className="flex-1 px-2 mt-2">
          {!sidebarCollapsed ? (
            <button
              onClick={handleNewChat}
              className="w-full flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-foreground bg-primary/10 hover:bg-primary/20 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span className="font-medium">New Chat</span>
            </button>
          ) : (
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center rounded-lg px-2 py-2 text-foreground bg-primary/10 hover:bg-primary/20 transition-colors"
              title="New Chat"
            >
              <Plus className="h-4 w-4" />
            </button>
          )}

          {!sidebarCollapsed && (
            <div className="mt-4 space-y-4 pb-4">
              {groupedSessions.pinned.length > 0 && (
                <ChatGroup
                  title="Pinned"
                  sessions={groupedSessions.pinned}
                  location={location}
                  onDelete={deleteSession}
                  onUpdate={updateSession}
                  onArchive={archiveSession}
                  onRestore={restoreSession}
                />
              )}
              {groupedSessions.today.length > 0 && (
                <ChatGroup title="Today" sessions={groupedSessions.today} location={location} onDelete={deleteSession} onUpdate={updateSession} onArchive={archiveSession} onRestore={restoreSession} />
              )}
              {groupedSessions.yesterday.length > 0 && (
                <ChatGroup title="Yesterday" sessions={groupedSessions.yesterday} location={location} onDelete={deleteSession} onUpdate={updateSession} onArchive={archiveSession} onRestore={restoreSession} />
              )}
              {groupedSessions.previous7Days.length > 0 && (
                <ChatGroup title="Previous 7 Days" sessions={groupedSessions.previous7Days} location={location} onDelete={deleteSession} onUpdate={updateSession} onArchive={archiveSession} onRestore={restoreSession} />
              )}
              {groupedSessions.older.length > 0 && (
                <ChatGroup title="Older" sessions={groupedSessions.older} location={location} onDelete={deleteSession} onUpdate={updateSession} onArchive={archiveSession} onRestore={restoreSession} />
              )}
            </div>
          )}
        </div>
      </div>

      <div className="h-px bg-border/50 mx-3" />

      <div className="p-3">
        <div className={cn('flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-muted/60 transition-colors cursor-default', sidebarCollapsed && 'justify-center')}>
          <div className="h-7 w-7 shrink-0 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-[11px] font-bold text-white shadow-sm ring-1 ring-white/10">
            {initials}
          </div>
          <AnimatePresence initial={false}>
            {!sidebarCollapsed && (
              <motion.div variants={sidebarLabelVariants} initial="collapsed" animate="expanded" exit="collapsed" className="flex flex-col overflow-hidden min-w-0">
                <span className="truncate text-xs font-medium text-foreground">
                  {user?.full_name || user?.email?.split('@')[0] || 'User'}
                </span>
                <Badge variant="subtle" className="w-fit text-[9px] h-3.5 mt-0.5 px-1.5 uppercase tracking-wider">
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

function ChatGroup({
  title,
  sessions,
  location,
  onDelete,
  onUpdate,
  onArchive,
  onRestore,
}: {
  title: string
  sessions: ChatSession[]
  location: ReturnType<typeof useLocation>
  onDelete: (id: string) => Promise<void>
  onUpdate: (id: string, updates: Partial<ChatSession>) => Promise<void>
  onArchive: (id: string) => Promise<void>
  onRestore: (id: string) => Promise<void>
}) {
  return (
    <div data-chat-group={title}>
      <div className="text-[10px] font-bold text-muted-foreground/90 tracking-widest uppercase mb-1.5 px-2">
        {title}
      </div>
      <div className="space-y-0.5">
        {sessions.map((session) => (
          <ChatItem
            key={session.id}
            session={session}
            location={location}
            onDelete={onDelete}
            onUpdate={onUpdate}
            onArchive={onArchive}
            onRestore={onRestore}
          />
        ))}
      </div>
    </div>
  )
}

function ChatItem({
  session,
  location,
  onDelete,
  onUpdate,
  onArchive,
  onRestore,
}: {
  session: ChatSession
  location: ReturnType<typeof useLocation>
  onDelete: (id: string) => Promise<void>
  onUpdate: (id: string, updates: Partial<ChatSession>) => Promise<void>
  onArchive: (id: string) => Promise<void>
  onRestore: (id: string) => Promise<void>
}) {
  const navigate = useNavigate()
  const isActive = location.pathname === `/chat/${session.id}`
  const [isHovered, setIsHovered] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [title, setTitle] = useState(session.title)
  const menuRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isEditing) {
      setTitle(session.title)
    }
  }, [session.title, isEditing])

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [isEditing])

  useEffect(() => {
    if (!isMenuOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsMenuOpen(false)
      }
    }

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isMenuOpen])

  const handleSave = () => {
    setIsEditing(false)
    const trimmed = title.trim()
    if (trimmed && trimmed !== session.title) {
      onUpdate(session.id, { title: trimmed })
    } else {
      setTitle(session.title)
    }
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setTitle(session.title)
  }

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMenuOpen(false)
    if (window.confirm('Are you sure you want to permanently delete this chat?')) {
      await onDelete(session.id)
      if (location.pathname === `/chat/${session.id}`) {
        navigate('/chat')
      }
    }
  }

  const handleTogglePin = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMenuOpen(false)
    onUpdate(session.id, { pinned: !session.pinned })
  }

  const handleStartRename = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMenuOpen(false)
    setIsEditing(true)
  }

  const handleToggleArchive = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsMenuOpen(false)
    if (session.archived) {
      onRestore(session.id)
    } else {
      onArchive(session.id)
    }
  }

  return (
    <div
      className="relative group"
      data-session-id={session.id}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isEditing ? (
        <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs bg-muted/60 border border-primary/50">
          <MessageSquare className="h-3.5 w-3.5 shrink-0 text-primary" />
          <input
            ref={inputRef}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSave()
              if (e.key === 'Escape') handleCancelEdit()
            }}
            className="flex-1 bg-transparent outline-none text-foreground text-xs"
            onClick={(e) => e.stopPropagation()}
            aria-label="Rename chat session"
          />
        </div>
      ) : (
        <div
          className={cn(
            'flex items-center justify-between rounded-md px-2 py-1.5 text-xs transition-colors',
            isActive
              ? 'bg-muted/80 text-foreground font-medium'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
        >
          <Link
            to={`/chat/${session.id}`}
            className="flex items-center gap-2 min-w-0 flex-1 truncate pr-1"
          >
            {session.pinned ? (
              <Pin className="h-3.5 w-3.5 shrink-0 text-primary fill-primary/30" />
            ) : (
              <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-70" />
            )}
            <span className="truncate">{session.title}</span>
          </Link>

          {/* Three-dot overflow menu button */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                setIsMenuOpen((prev) => !prev)
              }}
              className={cn(
                'p-1 rounded hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors',
                isMenuOpen || isHovered || isActive
                  ? 'opacity-100'
                  : 'opacity-0 group-hover:opacity-100 focus:opacity-100'
              )}
              title="More options"
              aria-label="Chat actions"
              aria-expanded={isMenuOpen}
            >
              <MoreHorizontal className="h-3.5 w-3.5" />
            </button>

            {/* Overflow Dropdown Menu */}
            {isMenuOpen && (
              <div
                className="absolute right-0 top-full mt-1 w-36 rounded-lg border border-border/80 bg-surface/95 backdrop-blur-md shadow-xl py-1 z-50 text-xs animate-in fade-in zoom-in-95 duration-100"
                role="menu"
                aria-orientation="vertical"
              >
                <button
                  onClick={handleTogglePin}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                  role="menuitem"
                >
                  <Pin className={cn('h-3.5 w-3.5', session.pinned && 'fill-current text-primary')} />
                  <span>{session.pinned ? 'Unpin' : 'Pin'}</span>
                </button>

                <button
                  onClick={handleStartRename}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                  role="menuitem"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  <span>Rename</span>
                </button>

                <button
                  onClick={handleToggleArchive}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                  role="menuitem"
                >
                  {session.archived ? (
                    <>
                      <ArchiveRestore className="h-3.5 w-3.5" />
                      <span>Restore</span>
                    </>
                  ) : (
                    <>
                      <Archive className="h-3.5 w-3.5" />
                      <span>Archive</span>
                    </>
                  )}
                </button>

                <div className="h-px bg-border/50 my-1" />

                <button
                  onClick={handleDelete}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left text-destructive hover:bg-destructive/10 transition-colors"
                  role="menuitem"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Delete</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
