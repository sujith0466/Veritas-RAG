import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Building2, Check, ChevronsUpDown, Plus, KeyRound, Loader2, AlertCircle } from 'lucide-react'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { workspaceService } from '@/services/workspaceService'
import { useToast } from '@/hooks/useToast'
import { Badge } from '@/components/common/Badge'
import { cn } from '@/utils/cn'
import type { UserWorkspaceMembership } from '@/types/workspaceOnboarding'

export function WorkspaceSelector() {
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)
  const switchWorkspace = useWorkspaceStore((s) => s.switchWorkspace)
  const user = useAuthStore((s) => s.user)
  const { toast } = useToast()

  const [memberships, setMemberships] = useState<UserWorkspaceMembership[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSwitching, setIsSwitching] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isOpen, setIsOpen] = useState(false)

  const loadMemberships = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await workspaceService.getUserWorkspaces()
      if (response?.items) {
        setMemberships(response.items)
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to load workspaces'
      setError(msg)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (user?.id) {
      loadMemberships()
    }
  }, [user?.id, currentWorkspace?.id, loadMemberships])

  const handleSwitch = async (targetId: string, targetName: string) => {
    if (targetId === currentWorkspace?.id) {
      setIsOpen(false)
      return
    }

    setIsSwitching(targetId)
    try {
      await switchWorkspace(targetId)
      toast({
        title: 'Workspace Switched',
        message: `Switched active workspace to ${targetName}`,
        type: 'success',
      })
      setIsOpen(false)
      await loadMemberships()
    } catch (err: any) {
      const detail =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        err.message ||
        'Failed to switch workspace'
      toast({
        title: 'Switch Failed',
        message: detail,
        type: 'error',
      })
    } finally {
      setIsSwitching(null)
    }
  }

  // Active workspace name and role
  const activeMembership = memberships.find(
    (m) => m.workspace_id === currentWorkspace?.id || m.is_active_context
  )
  const activeName = currentWorkspace?.name || activeMembership?.name || 'Select Workspace'
  const activeRole = (activeMembership?.role || user?.role || '').toUpperCase()

  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          aria-label="Workspace switcher"
          data-testid="workspace-selector-trigger"
          className="group flex h-9 items-center gap-2 rounded-lg border border-border/80 bg-surface/80 px-2.5 py-1.5 text-xs sm:text-sm font-medium text-foreground hover:bg-muted hover:border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-all duration-150 max-w-[200px] sm:max-w-[260px]"
        >
          <Building2 className="h-4 w-4 shrink-0 text-primary" />
          <span className="truncate font-semibold text-left">{activeName}</span>
          {activeRole && (
            <Badge
              variant="outline"
              className="hidden lg:inline-flex px-1.5 py-0 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground border-border/60"
            >
              {activeRole}
            </Badge>
          )}
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground ml-auto group-hover:text-foreground transition-colors" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          data-testid="workspace-selector-dropdown"
          className="z-50 w-64 sm:w-72 overflow-hidden rounded-lg border border-border bg-surface-elevated p-1 shadow-lg animate-in data-[side=bottom]:slide-in-from-top-2"
        >
          <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
            Workspaces
          </div>

          {isLoading && memberships.length === 0 ? (
            <div className="flex items-center justify-center py-4 text-xs text-muted-foreground gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Loading workspaces...</span>
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 px-2 py-2 text-xs text-destructive">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{error}</span>
            </div>
          ) : memberships.length === 0 ? (
            <div className="px-2 py-3 text-xs text-muted-foreground text-center">
              No workspaces found
            </div>
          ) : (
            <div className="max-h-56 overflow-y-auto space-y-0.5 py-0.5">
              {memberships.map((ws) => {
                const isActive = ws.workspace_id === currentWorkspace?.id || ws.is_active_context
                const isItemSwitching = isSwitching === ws.workspace_id

                return (
                  <DropdownMenu.Item
                    key={ws.workspace_id}
                    data-testid={`workspace-item-${ws.workspace_id}`}
                    disabled={isItemSwitching}
                    onClick={() => handleSwitch(ws.workspace_id, ws.name)}
                    className={cn(
                      'flex cursor-pointer select-none items-center justify-between rounded-md px-2 py-1.5 text-xs sm:text-sm outline-none transition-colors',
                      isActive
                        ? 'bg-primary/10 text-primary font-medium'
                        : 'hover:bg-muted focus:bg-muted text-foreground'
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Building2 className={cn('h-3.5 w-3.5 shrink-0', isActive ? 'text-primary' : 'text-muted-foreground')} />
                      <span className="truncate">{ws.name}</span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 ml-2">
                      <Badge
                        variant="secondary"
                        className="px-1.5 py-0 text-[10px] font-medium uppercase tracking-wider"
                      >
                        {ws.role}
                      </Badge>

                      {isItemSwitching ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                      ) : isActive ? (
                        <Check className="h-3.5 w-3.5 text-primary" />
                      ) : null}
                    </div>
                  </DropdownMenu.Item>
                )
              })}
            </div>
          )}

          <DropdownMenu.Separator className="-mx-1 my-1 h-px bg-border-subtle" />

          {/* Action: Create New Workspace */}
          <DropdownMenu.Item
            asChild
            className="flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 text-xs sm:text-sm font-medium text-foreground outline-none hover:bg-muted focus:bg-muted"
          >
            <Link
              to="/workspaces/new"
              data-testid="create-workspace-nav-btn"
              onClick={() => setIsOpen(false)}
              className="flex items-center w-full gap-2 text-primary hover:text-primary"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Create New Workspace</span>
            </Link>
          </DropdownMenu.Item>

          {/* Action: Join Workspace */}
          <DropdownMenu.Item
            asChild
            className="flex cursor-pointer select-none items-center rounded-md px-2 py-1.5 text-xs sm:text-sm text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus:bg-muted focus:text-foreground"
          >
            <Link
              to="/workspaces/join"
              data-testid="join-workspace-nav-btn"
              onClick={() => setIsOpen(false)}
              className="flex items-center w-full gap-2"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span>Join Workspace</span>
            </Link>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
