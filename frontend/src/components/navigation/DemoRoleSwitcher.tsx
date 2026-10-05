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
    badgeColor: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
  },
  {
    role: 'owner',
    label: 'Owner',
    description: 'Full workspace authority, quotas & deletion',
    icon: Crown,
    badgeColor: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  },
  {
    role: 'admin',
    label: 'Admin',
    description: 'Member management, uploads & workspace analytics',
    icon: Shield,
    badgeColor: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  },
  {
    role: 'member',
    label: 'Member',
    description: 'Document ingestion, grounded chat & vector sync',
    icon: Users,
    badgeColor: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  },
  {
    role: 'viewer',
    label: 'Viewer',
    description: 'Read-only search, citations & knowledge inspection',
    icon: Eye,
    badgeColor: 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30',
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
          whileHover={shouldReduceMotion ? undefined : { scale: 1.02 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
          className={`group relative inline-flex items-center gap-1.5 sm:gap-2 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide border transition-all duration-200 outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50 ${
            isSimulated
              ? 'bg-amber-500/10 border-amber-500/40 text-amber-300 hover:bg-amber-500/20 hover:border-amber-500/60 shadow-[0_0_12px_rgba(245,158,11,0.15)]'
              : 'bg-zinc-900/60 border-zinc-700/60 text-zinc-300 hover:bg-zinc-800 hover:border-zinc-600'
          }`}
        >
          {isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-400" />
          ) : (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
            </span>
          )}

          <span className="hidden sm:inline font-mono text-[10px] text-amber-400/90 font-bold uppercase tracking-wider">
            DEMO
          </span>
          <span className="hidden sm:inline text-zinc-500">·</span>
          <span className="uppercase text-[11px] font-bold tracking-wider text-foreground">
            {currentRoleConfig.label}
          </span>

          <ChevronDown
            className={`h-3 w-3 text-muted-foreground transition-transform duration-200 ${
              isOpen ? 'rotate-180 text-foreground' : ''
            }`}
          />
        </motion.button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 w-72 sm:w-80 rounded-xl border border-border/80 bg-surface-elevated/95 p-2 shadow-2xl backdrop-blur-xl animate-in fade-in-0 zoom-in-95 data-[side=bottom]:slide-in-from-top-2"
        >
          {/* Header Banner */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-border/60 mb-1">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400" />
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
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
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
                      ? 'bg-primary/10 text-foreground font-medium'
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
              <div className="my-1.5 h-px bg-border/60" />
              <DropdownMenu.Item
                disabled={isPending}
                onClick={handleReset}
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-amber-400 hover:bg-amber-500/10 hover:text-amber-300 cursor-pointer outline-none transition-colors"
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
