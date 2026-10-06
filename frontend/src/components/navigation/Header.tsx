import { useState, useRef, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { Menu, Moon, Sun, Monitor, Pencil, Check, KeyRound } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Breadcrumbs } from './Breadcrumbs'
import { UserMenu } from './UserMenu'
import { useUIStore } from '@/stores/uiStore'
import { useTheme } from '@/hooks/useTheme'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'
import { useChatStore } from '@/stores/chatStore'
import { cn } from '@/utils/cn'
import { Badge } from '../common/Badge'
import { NotificationBell } from '../common/NotificationBell'
import { DemoRoleSwitcher } from './DemoRoleSwitcher'
import { JoinAccessDialog } from './JoinAccessDialog'

function HeaderChatTitle() {
  const activeSession = useChatStore((s) => s.activeSession)
  const updateSession = useChatStore((s) => s.updateSession)
  const [isEditing, setIsEditing] = useState(false)
  const [title, setTitle] = useState(activeSession?.title || 'New Chat')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isEditing) {
      setTitle(activeSession?.title || 'New Chat')
    }
  }, [activeSession?.title, isEditing])

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus()
      inputRef.current?.select()
    }
  }, [isEditing])

  const handleSave = async () => {
    setIsEditing(false)
    const trimmed = title.trim()
    if (activeSession && trimmed && trimmed !== activeSession.title) {
      await updateSession(activeSession.id, { title: trimmed })
    } else {
      setTitle(activeSession?.title || 'New Chat')
    }
  }

  const handleCancel = () => {
    setIsEditing(false)
    setTitle(activeSession?.title || 'New Chat')
  }

  if (isEditing) {
    return (
      <div className="flex items-center gap-1.5 min-w-0">
        <input
          ref={inputRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSave()
            if (e.key === 'Escape') handleCancel()
          }}
          aria-label="Rename conversation"
          className="h-7 px-2 py-0.5 text-xs sm:text-sm font-semibold text-foreground bg-surface border border-primary/50 rounded-md outline-none focus:ring-1 focus:ring-primary shadow-xs w-44 sm:w-60 md:w-72"
        />
        <button
          type="button"
          onClick={handleSave}
          title="Save title"
          aria-label="Save title"
          className="h-7 w-7 shrink-0 inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors cursor-pointer"
        >
          <Check className="h-3.5 w-3.5 text-primary" />
        </button>
      </div>
    )
  }

  return (
    <div
      onClick={() => {
        if (activeSession) setIsEditing(true)
      }}
      title={activeSession ? 'Click to rename conversation' : undefined}
      className={cn(
        'group flex items-center gap-1.5 px-2 py-1 -ml-2 rounded-md transition-colors min-w-0',
        activeSession ? 'cursor-pointer hover:bg-muted/60' : 'cursor-default'
      )}
    >
      <span className="text-xs sm:text-sm font-semibold text-foreground tracking-tight truncate max-w-[180px] sm:max-w-[280px] md:max-w-[400px]">
        {activeSession?.title || 'New Chat'}
      </span>
      {activeSession && (
        <Pencil className="h-3 w-3 text-muted-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
      )}
    </div>
  )
}

export function Header() {
  const location = useLocation()
  const { toggleSidebar } = useUIStore()
  const { setMode, resolvedMode } = useTheme()
  const { isOnline } = useNetworkStatus()
  const isChat = location.pathname.startsWith('/chat')
  const [isJoinAccessOpen, setIsJoinAccessOpen] = useState(false)

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-md shrink-0">
      <div className="flex items-center gap-3 sm:gap-4 overflow-hidden min-w-0">
        <button
          onClick={toggleSidebar}
          className="md:hidden inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Menu className="h-4 w-4" />
        </button>
        {isChat ? (
          <HeaderChatTitle />
        ) : (
          <div className="hidden md:block">
            <Breadcrumbs />
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        {!isOnline && (
          <Badge variant="destructive" className="hidden sm:inline-flex px-2 py-0.5 text-[10px]">
            Offline Mode
          </Badge>
        )}

        <NotificationBell />

        <DemoRoleSwitcher />

        <button
          type="button"
          onClick={() => setIsJoinAccessOpen(true)}
          aria-label="Workspace Join Access"
          title="Workspace Join Access"
          className="group inline-flex h-9 w-9 items-center justify-center rounded-lg border border-transparent hover:border-border/60 text-muted-foreground hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:border-transparent active:scale-95 transition-all duration-200"
        >
          <KeyRound className="h-4 w-4 transition-transform duration-200 group-hover:scale-110 motion-reduce:group-hover:scale-100 text-muted-foreground group-hover:text-foreground" />
        </button>

        <JoinAccessDialog open={isJoinAccessOpen} onOpenChange={setIsJoinAccessOpen} />

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              aria-label="Toggle color theme"
              className="group inline-flex h-9 w-9 items-center justify-center rounded-lg border border-transparent hover:border-border/60 text-muted-foreground hover:bg-muted/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:border-transparent active:scale-95 transition-all duration-200"
            >
              {resolvedMode === 'dark' ? (
                <Moon className="h-4 w-4 transition-transform duration-300 group-hover:-rotate-12 motion-reduce:group-hover:rotate-0 text-muted-foreground group-hover:text-foreground" />
              ) : (
                <Sun className="h-4 w-4 transition-transform duration-300 group-hover:rotate-45 motion-reduce:group-hover:rotate-0 text-muted-foreground group-hover:text-foreground" />
              )}
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              className="z-50 min-w-[8rem] overflow-hidden rounded-md border border-border bg-surface-elevated p-1 shadow-md animate-in data-[side=bottom]:slide-in-from-top-2 data-[side=top]:slide-in-from-bottom-2"
            >
              <DropdownMenu.Item
                onClick={() => setMode('light')}
                className="flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-muted focus:bg-muted focus:text-foreground"
              >
                <Sun className="mr-2 h-4 w-4" />
                <span>Light</span>
              </DropdownMenu.Item>
              <DropdownMenu.Item
                onClick={() => setMode('dark')}
                className="flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-muted focus:bg-muted focus:text-foreground"
              >
                <Moon className="mr-2 h-4 w-4" />
                <span>Dark</span>
              </DropdownMenu.Item>
              <DropdownMenu.Item
                onClick={() => setMode('system')}
                className="flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-muted focus:bg-muted focus:text-foreground"
              >
                <Monitor className="mr-2 h-4 w-4" />
                <span>System</span>
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <UserMenu />
      </div>
    </header>
  )
}
