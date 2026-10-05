import React, { useState } from 'react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Sparkles,
  Shield,
  ShieldAlert,
  Users,
  Eye,
  Check,
  RotateCcw,
  ChevronDown,
  Loader2,
  Crown,
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { authService } from '@/services/auth/authService'
import type { Role } from '@/types'

interface DemoRoleOption {
  role: Role
  label: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  badgeColor: string
}

const DEMO_ROLES: DemoRoleOption[] = [
  {
    role: 'platform_admin',
    label: 'Platform Admin',
    description: 'System-wide governance, global metrics & compliance',
    icon: ShieldAlert,
    badgeColor: 'text-purple-700 bg-purple-50 border-purple-200 dark:text-purple-400 dark:bg-purple-500/10 dark:border-purple-500/30',
  },
  {
    role: 'owner',
    label: 'Owner',
    description: 'Full workspace authority, quotas & deletion',
    icon: Crown,
    badgeColor: 'text-amber-800 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-500/10 dark:border-amber-500/30',
  },
  {
    role: 'admin',
    label: 'Admin',
    description: 'Member management, uploads & workspace analytics',
    icon: Shield,
    badgeColor: 'text-blue-700 bg-blue-50 border-blue-200 dark:text-blue-400 dark:bg-blue-500/10 dark:border-blue-500/30',
  },
  {
    role: 'member',
    label: 'Member',
    description: 'Document ingestion, grounded chat & vector sync',
    icon: Users,
    badgeColor: 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-500/10 dark:border-emerald-500/30',
  },
  {
    role: 'viewer',
    label: 'Viewer',
    description: 'Read-only search, citations & knowledge inspection',
    icon: Eye,
    badgeColor: 'text-zinc-700 bg-zinc-100 border-zinc-200 dark:text-zinc-400 dark:bg-zinc-500/10 dark:border-zinc-500/30',
  },
]

export function DemoRoleSwitcher() {
  const { user, setAuth } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)
  const [isPending, setIsPending] = useState(false)
  const shouldReduceMotion = useReducedMotion()

  // STRICT REQUIREMENT: Only render if server-authoritative capability flag is true
  if (!user?.demo_role_switcher_enabled) {
    return null
  }

  const currentRole = user.role?.toLowerCase() || 'viewer'
  const isSimulated = Boolean(user.demo_simulated)
  const currentRoleConfig = DEMO_ROLES.find((r) => r.role === currentRole) || DEMO_ROLES[4]

  const handleRoleSelect = async (targetRole: Role) => {
    if (isPending || targetRole === currentRole) return
    setIsPending(true)
    try {
      const activeWorkspaceId = user.tenant_id || user.workspace_id || undefined
      const response = await authService.switchDemoRole(targetRole, activeWorkspaceId)

      // Store new access token and sync full backend profile
      useAuthStore.setState({ token: response.access_token })
      const updatedProfile = await authService.fetchBackendProfile()

      if (updatedProfile.tenant_id) {
        await useWorkspaceStore.getState().fetchCurrentWorkspace().catch(() => {})
      } else {
        useWorkspaceStore.getState().resetWorkspaceResolution()
      }

      setAuth(updatedProfile, response.access_token)

      // Cross-tab broadcast
      const channel = new BroadcastChannel('auth_sync')
      channel.postMessage({ type: 'DEMO_ROLE_SWITCHED', role: targetRole })
      channel.close()

      setIsOpen(false)
    } catch (err) {
      console.error('Failed to switch demo role:', err)
    } finally {
      setIsPending(false)
    }
  }

  const handleReset = async () => {
    if (isPending) return
    setIsPending(true)
    try {
      const response = await authService.resetDemoRole()

      useAuthStore.setState({ token: response.access_token })
      const updatedProfile = await authService.fetchBackendProfile()

      if (updatedProfile.tenant_id) {
        await useWorkspaceStore.getState().fetchCurrentWorkspace().catch(() => {})
      } else {
        useWorkspaceStore.getState().resetWorkspaceResolution()
      }

      setAuth(updatedProfile, response.access_token)

      // Cross-tab broadcast
      const channel = new BroadcastChannel('auth_sync')
      channel.postMessage({ type: 'DEMO_ROLE_RESET' })
      channel.close()

      setIsOpen(false)
    } catch (err) {
      console.error('Failed to reset demo role:', err)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <DropdownMenu.Root open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenu.Trigger asChild>
        <motion.button
          type="button"
          aria-label="Demo Role Switcher"
          disabled={isPending}
          whileHover={shouldReduceMotion ? undefined : { scale: 1.01 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.99 }}
          className={`group relative inline-flex items-center gap-1.5 sm:gap-2 px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full text-xs font-medium tracking-normal border transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-primary/50 shadow-xs ${
            isSimulated
              ? 'bg-amber-50/90 border-amber-300 text-amber-900 hover:bg-amber-100/90 hover:border-amber-400 shadow-[0_1px_3px_rgba(217,119,6,0.1)] dark:bg-amber-500/10 dark:border-amber-500/40 dark:text-amber-300 dark:hover:bg-amber-500/20 dark:hover:border-amber-500/60 dark:shadow-[0_0_12px_rgba(245,158,11,0.15)]'
              : 'bg-surface border-border text-foreground hover:bg-muted/70 hover:border-border/90 shadow-[0_1px_2px_rgba(0,0,0,0.04)] dark:bg-zinc-900/60 dark:border-zinc-700/60 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:border-zinc-600'
          }`}
        >
          {isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-600 dark:text-amber-400" />
          ) : (
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isSimulated ? 'bg-amber-500 dark:bg-amber-400' : 'bg-primary/60 dark:bg-primary/60'
              }`} />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${
                isSimulated ? 'bg-amber-600 dark:bg-amber-500' : 'bg-primary dark:bg-primary'
              }`} />
            </span>
          )}

          <span className="hidden sm:inline font-mono text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-800 border border-amber-500/25 dark:bg-amber-500/20 dark:text-amber-300 dark:border-amber-500/30">
            DEMO
          </span>
          <span className="hidden sm:inline text-border font-light select-none">|</span>
          <span className="uppercase text-[11px] font-bold tracking-wider text-foreground">
            {currentRoleConfig.label}
          </span>

          <ChevronDown
            className={`h-3 w-3 text-muted-foreground transition-transform duration-200 group-hover:text-foreground ${
              isOpen ? 'rotate-180 text-foreground' : ''
            }`}
          />
        </motion.button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 w-72 sm:w-80 rounded-xl border border-border bg-surface dark:bg-surface-elevated/95 p-2 shadow-xl backdrop-blur-xl animate-in fade-in-0 zoom-in-95 data-[side=bottom]:slide-in-from-top-2"
        >
          {/* Header Banner */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/80 mb-1.5 bg-muted/40 dark:bg-transparent rounded-t-lg">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-foreground">
                  Demo Mode Control
                </p>
                <p className="text-[10px] text-muted-foreground">
                  Simulate RBAC roles dynamically
                </p>
              </div>
            </div>
            {isSimulated && (
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-800 border border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-400">
                Simulated
              </span>
            )}
          </div>

          {/* Role Options */}
          <div className="space-y-1">
            {DEMO_ROLES.map((roleOpt) => {
              const isSelected = currentRole === roleOpt.role
              const Icon = roleOpt.icon

              return (
                <DropdownMenu.Item
                  key={roleOpt.role}
                  disabled={isPending}
                  onClick={() => handleRoleSelect(roleOpt.role)}
                  className={`relative flex items-start gap-3 rounded-lg px-3 py-2 text-xs outline-none cursor-pointer transition-all duration-150 ${
                    isSelected
                      ? 'bg-primary/10 text-foreground font-medium ring-1 ring-primary/20 dark:ring-primary/30'
                      : 'hover:bg-muted text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <div
                    className={`mt-0.5 p-1.5 rounded-md border shrink-0 ${roleOpt.badgeColor}`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-foreground text-xs">
                        {roleOpt.label}
                      </span>
                      {isSelected && (
                        <Check className="h-3.5 w-3.5 text-primary shrink-0 ml-2" />
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-snug mt-0.5">
                      {roleOpt.description}
                    </p>
                  </div>
                </DropdownMenu.Item>
              )
            })}
          </div>

          {/* Reset to Base Role Action */}
          {isSimulated && (
            <>
              <div className="my-1.5 h-px bg-border/80" />
              <DropdownMenu.Item
                disabled={isPending}
                onClick={handleReset}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-amber-700 hover:bg-amber-500/10 hover:text-amber-800 dark:text-amber-400 dark:hover:bg-amber-500/10 dark:hover:text-amber-300 cursor-pointer outline-none transition-colors"
              >
                <RotateCcw className="h-3.5 w-3.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="font-semibold">Reset to Base Role</p>
                  <p className="text-[10px] text-muted-foreground">
                    Restores authentic database permissions
                  </p>
                </div>
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
