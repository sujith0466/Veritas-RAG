import { useEffect, useState, useMemo } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
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
  MessageSquare,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Pin
} from 'lucide-react'
import { isToday, isYesterday, isThisWeek, parseISO } from 'date-fns'

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
      { name: 'Knowledge', href: '/knowledge', icon: Brain },
      { name: 'Documents', href: '/documents', icon: FileText },
    ],
  },
  {
    group: '',
    items: [
      { name: 'Chunks', href: '/chunks', icon: Layers, adminOnly: true },
      { name: 'Embeddings', href: '/embeddings', icon: Cpu, adminOnly: true },
      { name: 'Vectors', href: '/vectors', icon: Database, adminOnly: true },
    ],
  },
  {
    group: '',
    items: [
      { name: 'AI Chat', href: '/chat', icon: MessageSquare, matchPrefix: true },
      { name: 'AI Reliability', href: '/analytics', icon: BarChart3 },
    ],
  },
  {
    group: '',
    items: [
      { name: 'System Health', href: '/health', icon: Activity, adminOnly: true },
      { name: 'Diagnostics', href: '/diagnostics', icon: Terminal, adminOnly: true },
    ],
  },
]

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const user = useAuthStore((s) => s.user)
  
  const { sessions, fetchSessions, createSession, updateSession, deleteSession } = useChatStore()

  useEffect(() => {
    fetchSessions()
  }, [])

  const handleNewChat = async () => {
    const session = await createSession()
    navigate(`/chat/${session.id}`)
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
      if (isToday(date)) groups.today.push(session)
      else if (isYesterday(date)) groups.yesterday.push(session)
      else if (isThisWeek(date)) groups.previous7Days.push(session)
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
                  RAGuard AI
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
            const items = section.items.filter(item => !item.adminOnly || user?.role === 'admin')
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
                />
              )}
              {groupedSessions.today.length > 0 && (
                <ChatGroup title="Today" sessions={groupedSessions.today} location={location} onDelete={deleteSession} onUpdate={updateSession} />
              )}
              {groupedSessions.yesterday.length > 0 && (
                <ChatGroup title="Yesterday" sessions={groupedSessions.yesterday} location={location} onDelete={deleteSession} onUpdate={updateSession} />
              )}
              {groupedSessions.previous7Days.length > 0 && (
                <ChatGroup title="Previous 7 Days" sessions={groupedSessions.previous7Days} location={location} onDelete={deleteSession} onUpdate={updateSession} />
              )}
              {groupedSessions.older.length > 0 && (
                <ChatGroup title="Older" sessions={groupedSessions.older} location={location} onDelete={deleteSession} onUpdate={updateSession} />
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

function ChatGroup({ title, sessions, location, onDelete, onUpdate }: { title: string, sessions: ChatSession[], location: any, onDelete: any, onUpdate: any }) {
  return (
    <div>
      <div className="text-[10px] font-semibold text-muted-foreground/70 tracking-widest uppercase mb-1.5 px-2">
        {title}
      </div>
      <div className="space-y-0.5">
        {sessions.map(session => (
          <ChatItem key={session.id} session={session} location={location} onDelete={onDelete} onUpdate={onUpdate} />
        ))}
      </div>
    </div>
  )
}

function ChatItem({ session, location, onDelete, onUpdate }: { session: ChatSession, location: any, onDelete: any, onUpdate: any }) {
  const isActive = location.pathname === `/chat/${session.id}`
  const [isHovered, setIsHovered] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [title, setTitle] = useState(session.title)

  const handleSave = () => {
    setIsEditing(false)
    if (title.trim() && title !== session.title) {
      onUpdate(session.id, { title })
    }
  }

  return (
    <div 
      className="relative group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <Link
        to={`/chat/${session.id}`}
        className={cn(
          "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs transition-colors",
          isActive ? "bg-muted/80 text-foreground font-medium" : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
        )}
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-70" />
        {isEditing ? (
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => e.key === 'Enter' && handleSave()}
            className="flex-1 bg-background border border-primary/50 rounded px-1 outline-none text-foreground"
            onClick={e => e.preventDefault()}
          />
        ) : (
          <span className="truncate flex-1">{session.title}</span>
        )}
      </Link>
      
      {(isHovered || isActive) && !isEditing && (
        <div className="absolute right-1 top-1.5 flex items-center gap-1 bg-gradient-to-l from-muted/80 via-muted/80 to-transparent pl-4 pr-1">
          <button onClick={(e) => { e.preventDefault(); onUpdate(session.id, { pinned: !session.pinned }) }} className="p-1 hover:text-foreground text-muted-foreground transition-colors" title={session.pinned ? "Unpin" : "Pin"}>
            <Pin className={cn("h-3 w-3", session.pinned && "fill-current text-foreground")} />
          </button>
          <button onClick={(e) => { e.preventDefault(); setIsEditing(true) }} className="p-1 hover:text-foreground text-muted-foreground transition-colors">
            <Pencil className="h-3 w-3" />
          </button>
          <button onClick={(e) => { e.preventDefault(); onDelete(session.id) }} className="p-1 hover:text-destructive text-muted-foreground transition-colors">
            <Trash2 className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  )
}
