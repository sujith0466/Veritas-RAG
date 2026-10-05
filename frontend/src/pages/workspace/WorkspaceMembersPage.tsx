import React, { useEffect, useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { useMemberStore } from '@/stores/memberStore'
import { invitationService } from '@/services/invitationService'
import type { WorkspaceInvitation } from '@/types/workspaceInvitation'
import {
  Users,
  UserPlus,
  Search,
  UserX,
  UserCheck,
  Trash2,
  Mail,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Clock,
  X,
  Crown,
  Info,
  Shield,
  Eye,
  RotateCw,
  Ban,
  ChevronDown,
} from 'lucide-react'

import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Label } from '@/components/common/Label'
import { Card } from '@/components/common/Card'
import { cn } from '@/utils/cn'

interface ConfirmActionState {
  type: 'suspend' | 'restore' | 'remove' | 'bulk_suspend' | 'bulk_restore' | 'bulk_remove'
  memberId?: string
  memberName?: string
  memberCount?: number
}

const ROLE_DEFINITIONS = [
  {
    role: 'OWNER',
    title: 'Workspace Owner',
    icon: Crown,
    color: 'text-amber-500 bg-amber-500/10 border-amber-500/25',
    description: 'Supreme control over billing, quotas, member lifecycle, and workspace deletion. Protected from demotion.',
  },
  {
    role: 'ADMIN',
    title: 'Administrator',
    icon: ShieldCheck,
    color: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/25',
    description: 'Can invite members, manage non-owner roles, configure quotas, and inspect security audit logs.',
  },
  {
    role: 'MEMBER',
    title: 'Team Member',
    icon: Users,
    color: 'text-sky-400 bg-sky-500/10 border-sky-500/25',
    description: 'Can query knowledge bases, execute chat sessions, and upload documents within quota limits.',
  },
  {
    role: 'VIEWER',
    title: 'Read-Only Viewer',
    icon: Eye,
    color: 'text-slate-400 bg-slate-500/10 border-slate-500/25',
    description: 'Strict read-only access to documents, analytics, and session history without operational mutation rights.',
  },
]

export const WorkspaceMembersPage: React.FC = () => {
  const { workspaceId: paramWorkspaceId } = useParams<{ workspaceId: string }>()
  const user = useAuthStore(s => s.user)
  const currentWorkspace = useWorkspaceStore(s => s.currentWorkspace)
  const shouldReduceMotion = useReducedMotion()

  const workspaceId = paramWorkspaceId || currentWorkspace?.id || user?.workspace_id || user?.tenant_id || user?.workspace_name
  const {
    members,
    total,
    isLoading,
    error,
    fetchMembers,
    updateRole,
    suspendMember,
    restoreMember,
    removeMember,
    bulkManage,
    clearError,
  } = useMemberStore()

  const [activeTab, setActiveTab] = useState<'members' | 'invitations'>('members')
  const [search, setSearch] = useState<string>('')
  const [roleFilter, setRoleFilter] = useState<string>('')
  const [selectedMembers, setSelectedMembers] = useState<string[]>([])
  const [showRoleGuide, setShowRoleGuide] = useState<boolean>(false)

  // Confirmation Modal state
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null)
  const [isActionExecuting, setIsActionExecuting] = useState<boolean>(false)

  // Invite modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState<boolean>(false)
  const [inviteEmail, setInviteEmail] = useState<string>('')
  const [inviteRole, setInviteRole] = useState<string>('MEMBER')
  const [inviteMessage, setInviteMessage] = useState<string>('')
  const [sendingInvite, setSendingInvite] = useState<boolean>(false)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  // Invitations list state
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([])
  const [loadingInvitations, setLoadingInvitations] = useState<boolean>(false)

  const isCurrentUserOwner = String(user?.role || '').trim().toUpperCase() === 'OWNER'

  useEffect(() => {
    if (workspaceId) {
      fetchMembers(workspaceId, { search, role: roleFilter || undefined })
      if (activeTab === 'invitations') {
        loadInvitations()
      }
    }
  }, [workspaceId, search, roleFilter, activeTab])

  const loadInvitations = async () => {
    if (!workspaceId) return
    try {
      setLoadingInvitations(true)
      const res = await invitationService.listInvitations(workspaceId)
      setInvitations(res.items)
    } catch (err) {
      console.error('Failed to load invitations', err)
    } finally {
      setLoadingInvitations(false)
    }
  }

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId || !inviteEmail) return
    try {
      setSendingInvite(true)
      clearError()
      await invitationService.sendInvitation(workspaceId, {
        email: inviteEmail,
        role: inviteRole,
        custom_message: inviteMessage || undefined,
      })
      setInviteSuccess(`Invitation sent to ${inviteEmail}`)
      setInviteEmail('')
      setInviteMessage('')
      setTimeout(() => {
        setIsInviteModalOpen(false)
        setInviteSuccess(null)
        if (activeTab === 'invitations') loadInvitations()
      }, 1500)
    } catch (err: any) {
      console.error('Failed to send invitation', err)
    } finally {
      setSendingInvite(false)
    }
  }

  const handleRevokeInvitation = async (invitationId: string) => {
    if (!workspaceId) return
    try {
      await invitationService.revokeInvitation(workspaceId, invitationId)
      await loadInvitations()
    } catch (err) {
      console.error('Failed to revoke invitation', err)
    }
  }

  const handleResendInvitation = async (invitationId: string) => {
    if (!workspaceId) return
    try {
      await invitationService.resendInvitation(workspaceId, invitationId)
      await loadInvitations()
    } catch (err) {
      console.error('Failed to resend invitation', err)
    }
  }

  const handleToggleSelectAll = () => {
    const selectable = members.filter(m => m.role !== 'OWNER').map(m => m.id)
    if (selectedMembers.length === selectable.length && selectable.length > 0) {
      setSelectedMembers([])
    } else {
      setSelectedMembers(selectable)
    }
  }

  const handleToggleSelect = (id: string) => {
    setSelectedMembers(prev => (prev.includes(id) ? prev.filter(mid => mid !== id) : [...prev, id]))
  }

  // Execute confirmed modal action
  const handleExecuteConfirmAction = async () => {
    if (!confirmAction || !workspaceId) return
    setIsActionExecuting(true)
    try {
      if (confirmAction.type === 'suspend' && confirmAction.memberId) {
        await suspendMember(workspaceId, confirmAction.memberId)
      } else if (confirmAction.type === 'restore' && confirmAction.memberId) {
        await restoreMember(workspaceId, confirmAction.memberId)
      } else if (confirmAction.type === 'remove' && confirmAction.memberId) {
        await removeMember(workspaceId, confirmAction.memberId)
      } else if (confirmAction.type === 'bulk_suspend') {
        await bulkManage(workspaceId, { action: 'suspend', member_ids: selectedMembers })
        setSelectedMembers([])
      } else if (confirmAction.type === 'bulk_restore') {
        await bulkManage(workspaceId, { action: 'restore', member_ids: selectedMembers })
        setSelectedMembers([])
      } else if (confirmAction.type === 'bulk_remove') {
        await bulkManage(workspaceId, { action: 'remove', member_ids: selectedMembers })
        setSelectedMembers([])
      }
      setConfirmAction(null)
    } catch (err) {
      console.error('Action failed', err)
    } finally {
      setIsActionExecuting(false)
    }
  }

  const ownersAndAdminsCount = useMemo(
    () => members.filter(m => m.role === 'OWNER' || m.role === 'ADMIN').length,
    [members]
  )

  const getRoleBadge = (role: string) => {
    switch (role?.toUpperCase()) {
      case 'OWNER':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/30">
            <Crown className="h-3 w-3" />
            OWNER
          </span>
        )
      case 'ADMIN':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/25">
            <ShieldCheck className="h-3 w-3" />
            ADMIN
          </span>
        )
      case 'MEMBER':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-sky-500/10 text-sky-400 border border-sky-500/25">
            <Users className="h-3 w-3" />
            MEMBER
          </span>
        )
      case 'VIEWER':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-slate-500/10 text-slate-400 border border-slate-500/25">
            <Eye className="h-3 w-3" />
            VIEWER
          </span>
        )
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      <AdminPageHeader
        eyebrow="ADMINISTRATION / TEAM"
        title="Members & Access"
        description="Administer workspace team members, invitations, granular role assignments, and authentication boundaries."
        badge={
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-2xs font-mono font-medium bg-primary/10 text-primary border border-primary/20">
            <Users className="h-3 w-3" />
            {total} Active Seat{total !== 1 ? 's' : ''}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowRoleGuide(!showRoleGuide)}
              className="flex items-center gap-1.5 text-xs"
            >
              <Info className="h-3.5 w-3.5 text-muted-foreground" />
              <span>Role Permissions</span>
              <ChevronDown className={cn('h-3.5 w-3.5 transition-transform duration-200', showRoleGuide && 'rotate-180')} />
            </Button>
            <Button onClick={() => setIsInviteModalOpen(true)} className="flex items-center gap-2 shadow-xs" size="sm">
              <UserPlus className="h-4 w-4" />
              <span>Invite Team Member</span>
            </Button>
          </div>
        }
      />

      {/* Role Authority & Permissions Guide Panel */}
      <AnimatePresence>
        {showRoleGuide && (
          <motion.div
            initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <Card className="p-5 border border-border/80 bg-card/60 backdrop-blur-sm shadow-sm space-y-3">
              <div className="flex items-center justify-between border-b border-border/50 pb-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Shield className="h-4 w-4 text-primary" />
                  <span>Canonical Role Hierarchy & Permissions</span>
                </div>
                <span className="text-2xs font-mono text-muted-foreground">Authoritative Backend RBAC</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
                {ROLE_DEFINITIONS.map(def => {
                  const Icon = def.icon
                  return (
                    <div key={def.role} className="p-3 rounded-lg bg-card border border-border/60 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <div className={cn('p-1.5 rounded-md border', def.color)}>
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <span className="font-semibold text-xs text-foreground font-mono">{def.title}</span>
                      </div>
                      <p className="text-2xs text-muted-foreground leading-relaxed">{def.description}</p>
                    </div>
                  )
                })}
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between bg-card hover:border-border transition-colors">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Total Active Members
            </span>
            <div className="text-2xl font-bold text-foreground mt-1 font-mono">{total}</div>
          </div>
          <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
            <Users className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between bg-card hover:border-border transition-colors">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Administrators & Owners
            </span>
            <div className="text-2xl font-bold text-foreground mt-1 font-mono">{ownersAndAdminsCount}</div>
          </div>
          <div className="p-2.5 bg-indigo-500/10 rounded-lg text-indigo-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between bg-card hover:border-border transition-colors">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Pending Invitations
            </span>
            <div className="text-2xl font-bold text-foreground mt-1 font-mono">{invitations.length}</div>
          </div>
          <div className="p-2.5 bg-amber-500/10 rounded-lg text-amber-400">
            <Clock className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border gap-6 pt-2">
        <button
          onClick={() => setActiveTab('members')}
          className={cn(
            'pb-3 text-sm font-medium transition-all border-b-2 flex items-center gap-2 cursor-pointer',
            activeTab === 'members'
              ? 'border-primary text-primary font-semibold'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Users className="h-4 w-4" />
          <span>Active Members ({total})</span>
        </button>
        <button
          onClick={() => setActiveTab('invitations')}
          className={cn(
            'pb-3 text-sm font-medium transition-all border-b-2 flex items-center gap-2 cursor-pointer',
            activeTab === 'invitations'
              ? 'border-primary text-primary font-semibold'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Mail className="h-4 w-4" />
          <span>Pending Invitations ({invitations.length})</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30 flex items-center gap-3 text-destructive text-sm animate-in fade-in">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={clearError} className="text-xs hover:underline font-mono cursor-pointer">Dismiss</button>
        </div>
      )}

      {activeTab === 'members' && (
        <div className="space-y-4">
          {/* Filters & Bulk Actions Toolbar */}
          <div className="flex flex-col sm:flex-row justify-between gap-3 items-stretch sm:items-center bg-card p-3 rounded-xl border border-border/80 shadow-xs">
            <div className="flex flex-1 items-center gap-3">
              <div className="relative flex-1">
                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search members by email or name..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 pr-8 h-9 text-xs bg-background/80"
                />
                {search && (
                  <button
                    onClick={() => setSearch('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              <select
                value={roleFilter}
                onChange={e => setRoleFilter(e.target.value)}
                className="h-9 px-3 bg-background border border-input rounded-md text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer font-mono"
              >
                <option value="">All Roles</option>
                <option value="OWNER">Owner</option>
                <option value="ADMIN">Admin</option>
                <option value="MEMBER">Member</option>
                <option value="VIEWER">Viewer</option>
              </select>
            </div>

            {selectedMembers.length > 0 && (
              <div className="flex items-center gap-2 text-xs font-medium pl-2 sm:border-l sm:border-border">
                <span className="text-muted-foreground font-mono text-2xs">{selectedMembers.length} selected:</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmAction({ type: 'bulk_suspend', memberCount: selectedMembers.length })}
                  className="h-7 text-2xs text-amber-500 border-amber-500/30 hover:bg-amber-500/10 cursor-pointer"
                >
                  Suspend
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmAction({ type: 'bulk_restore', memberCount: selectedMembers.length })}
                  className="h-7 text-2xs text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 cursor-pointer"
                >
                  Restore
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmAction({ type: 'bulk_remove', memberCount: selectedMembers.length })}
                  className="h-7 text-2xs text-destructive border-destructive/30 hover:bg-destructive/10 cursor-pointer"
                >
                  Remove
                </Button>
              </div>
            )}
          </div>

          {/* Members Table */}
          <div className="bg-card border border-border/80 rounded-xl overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-foreground">
                <thead className="bg-muted/40 text-2xs uppercase text-muted-foreground font-mono tracking-wider border-b border-border/80">
                  <tr>
                    <th className="p-3.5 w-10">
                      <input
                        type="checkbox"
                        checked={selectedMembers.length > 0 && selectedMembers.length === members.filter(m => m.role !== 'OWNER').length}
                        onChange={handleToggleSelectAll}
                        className="rounded border-input bg-background text-primary focus:ring-primary cursor-pointer"
                      />
                    </th>
                    <th className="p-3.5 font-semibold">User Profile</th>
                    <th className="p-3.5 font-semibold">Assigned Role</th>
                    <th className="p-3.5 font-semibold">Status</th>
                    <th className="p-3.5 font-semibold">Joined Date</th>
                    <th className="p-3.5 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {isLoading ? (
                    <tr>
                      <td colSpan={6} className="text-center py-12 text-muted-foreground">
                        <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary mb-2" />
                        <span className="text-xs font-mono">Loading team members...</span>
                      </td>
                    </tr>
                  ) : members.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="text-center py-12 text-muted-foreground">
                        <Users className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                        <div className="text-sm font-medium text-foreground">No members found</div>
                        <p className="text-xs text-muted-foreground mt-1">Try adjusting your search query or role filter.</p>
                      </td>
                    </tr>
                  ) : (
                    members.map(member => {
                      const isOwner = member.role === 'OWNER'
                      const isSuspended = member.status === 'SUSPENDED'
                      const displayName = member.user?.display_name || member.user?.username || ''
                      const email = member.user?.email || member.user_id

                      return (
                        <tr
                          key={member.id}
                          className={cn(
                            'hover:bg-muted/30 transition-colors',
                            isOwner && 'bg-amber-500/[0.02]',
                            isSuspended && 'opacity-70 bg-muted/20'
                          )}
                        >
                          <td className="p-3.5">
                            {!isOwner ? (
                              <input
                                type="checkbox"
                                checked={selectedMembers.includes(member.id)}
                                onChange={() => handleToggleSelect(member.id)}
                                className="rounded border-input bg-background text-primary focus:ring-primary cursor-pointer"
                              />
                            ) : (
                              <div className="h-4 w-4 flex items-center justify-center text-amber-500/60" title="Owner cannot be bulk-managed">
                                <Crown className="h-3 w-3" />
                              </div>
                            )}
                          </td>
                          <td className="p-3.5">
                            <div className="flex items-center gap-3">
                              <div
                                className={cn(
                                  'h-8 w-8 rounded-full border flex items-center justify-center text-xs font-bold shrink-0',
                                  isOwner
                                    ? 'bg-amber-500/15 border-amber-500/30 text-amber-500'
                                    : 'bg-primary/10 border-primary/20 text-primary'
                                )}
                              >
                                {email?.[0]?.toUpperCase() || 'U'}
                              </div>
                              <div className="truncate max-w-[240px]">
                                <div className="font-medium text-foreground text-sm flex items-center gap-1.5 truncate">
                                  <span>{displayName || email}</span>
                                  {isOwner && (
                                    <span title="Workspace Owner">
                                      <Crown className="h-3.5 w-3.5 text-amber-500 shrink-0" />
                                    </span>
                                  )}
                                </div>
                                {displayName && (
                                  <div className="text-2xs text-muted-foreground font-mono truncate">{email}</div>
                                )}
                              </div>
                            </div>
                          </td>
                          <td className="p-3.5">
                            {isOwner ? (
                              getRoleBadge('OWNER')
                            ) : (
                              <select
                                value={member.role}
                                onChange={e => workspaceId && updateRole(workspaceId, member.id, e.target.value)}
                                className="border border-border/80 rounded-md px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary bg-background cursor-pointer"
                              >
                                <option value="ADMIN">ADMIN</option>
                                <option value="MEMBER">MEMBER</option>
                                <option value="VIEWER">VIEWER</option>
                              </select>
                            )}
                          </td>
                          <td className="p-3.5">
                            <span
                              className={cn(
                                'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-2xs font-semibold font-mono border',
                                member.status === 'ACTIVE'
                                  ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                  : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                              )}
                            >
                              <span
                                className={cn(
                                  'h-1.5 w-1.5 rounded-full',
                                  member.status === 'ACTIVE' ? 'bg-emerald-500' : 'bg-amber-500'
                                )}
                              />
                              {member.status}
                            </span>
                          </td>
                          <td className="p-3.5 text-xs text-muted-foreground font-mono">
                            {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'N/A'}
                          </td>
                          <td className="p-3.5 text-right space-x-1 whitespace-nowrap">
                            {!isOwner ? (
                              <>
                                {member.status === 'ACTIVE' ? (
                                  <button
                                    onClick={() =>
                                      setConfirmAction({
                                        type: 'suspend',
                                        memberId: member.id,
                                        memberName: displayName || email,
                                      })
                                    }
                                    title="Suspend Member"
                                    className="p-1.5 rounded-md text-muted-foreground hover:text-amber-500 hover:bg-muted transition-colors cursor-pointer"
                                  >
                                    <UserX className="h-4 w-4" />
                                  </button>
                                ) : (
                                  <button
                                    onClick={() =>
                                      setConfirmAction({
                                        type: 'restore',
                                        memberId: member.id,
                                        memberName: displayName || email,
                                      })
                                    }
                                    title="Restore Member"
                                    className="p-1.5 rounded-md text-muted-foreground hover:text-emerald-500 hover:bg-muted transition-colors cursor-pointer"
                                  >
                                    <UserCheck className="h-4 w-4" />
                                  </button>
                                )}
                                <button
                                  onClick={() =>
                                    setConfirmAction({
                                      type: 'remove',
                                      memberId: member.id,
                                      memberName: displayName || email,
                                    })
                                  }
                                  title="Remove Member"
                                  className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition-colors cursor-pointer"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </>
                            ) : (
                              <span className="text-2xs text-muted-foreground/60 italic font-mono pr-2">Protected</span>
                            )}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'invitations' && (
        <div className="bg-card border border-border/80 rounded-xl overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-foreground">
              <thead className="bg-muted/40 text-2xs uppercase text-muted-foreground font-mono tracking-wider border-b border-border/80">
                <tr>
                  <th className="p-3.5 font-semibold">Recipient Email</th>
                  <th className="p-3.5 font-semibold">Assigned Role</th>
                  <th className="p-3.5 font-semibold">Status</th>
                  <th className="p-3.5 font-semibold">Expires At</th>
                  <th className="p-3.5 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {loadingInvitations ? (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-muted-foreground">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary mb-2" />
                      <span className="text-xs font-mono">Loading pending invitations...</span>
                    </td>
                  </tr>
                ) : invitations.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-muted-foreground">
                      <Mail className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                      <div className="text-sm font-medium text-foreground">No invitations currently pending</div>
                      <p className="text-xs text-muted-foreground mt-1">Send an invitation above to grant workspace access.</p>
                    </td>
                  </tr>
                ) : (
                  invitations.map(inv => (
                    <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                      <td className="p-3.5 font-medium text-foreground text-sm font-mono">
                        {inv.email}
                      </td>
                      <td className="p-3.5">
                        {getRoleBadge(inv.role)}
                      </td>
                      <td className="p-3.5">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold font-mono border',
                            inv.status === 'PENDING'
                              ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                              : inv.status === 'ACCEPTED'
                              ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                              : 'bg-muted text-muted-foreground border-border/60'
                          )}
                        >
                          <Clock className="h-3 w-3" />
                          {inv.status}
                        </span>
                      </td>
                      <td className="p-3.5 text-xs text-muted-foreground font-mono">
                        {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="p-3.5 text-right space-x-1.5 whitespace-nowrap">
                        {inv.status === 'PENDING' && (
                          <>
                            <button
                              onClick={() => handleResendInvitation(inv.id)}
                              title="Resend Invitation Email"
                              className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-muted transition-colors cursor-pointer"
                            >
                              <RotateCw className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => handleRevokeInvitation(inv.id)}
                              title="Revoke Invitation"
                              className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-muted transition-colors cursor-pointer"
                            >
                              <Ban className="h-4 w-4" />
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* In-App Confirmation Dialog Modal */}
      <AnimatePresence>
        {confirmAction && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xs p-4">
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="w-full max-w-md bg-card border border-border rounded-xl shadow-xl p-6 space-y-4"
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    'p-2.5 rounded-lg shrink-0',
                    confirmAction.type.includes('remove')
                      ? 'bg-destructive/10 text-destructive'
                      : confirmAction.type.includes('suspend')
                      ? 'bg-amber-500/10 text-amber-500'
                      : 'bg-emerald-500/10 text-emerald-500'
                  )}
                >
                  {confirmAction.type.includes('remove') ? (
                    <Trash2 className="h-5 w-5" />
                  ) : confirmAction.type.includes('suspend') ? (
                    <UserX className="h-5 w-5" />
                  ) : (
                    <UserCheck className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-foreground">
                    {confirmAction.type.includes('remove')
                      ? 'Confirm Member Removal'
                      : confirmAction.type.includes('suspend')
                      ? 'Confirm Member Suspension'
                      : 'Confirm Member Restoration'}
                  </h3>
                  <p className="text-2xs text-muted-foreground font-mono mt-0.5">Authoritative Lifecycle Transition</p>
                </div>
              </div>

              <div className="p-3 bg-muted/30 rounded-lg border border-border/60 text-xs text-muted-foreground space-y-1">
                {confirmAction.memberName && (
                  <p>
                    Target Member: <span className="font-semibold text-foreground">{confirmAction.memberName}</span>
                  </p>
                )}
                {confirmAction.memberCount && (
                  <p>
                    Target Count: <span className="font-semibold text-foreground">{confirmAction.memberCount} selected members</span>
                  </p>
                )}
                {confirmAction.type.includes('suspend') && (
                  <p className="text-amber-500/90 pt-1 text-2xs">
                    Security note: Suspending immediately revokes active JWT tokens in Redis. The user will be disconnected.
                  </p>
                )}
                {confirmAction.type.includes('remove') && (
                  <p className="text-destructive/90 pt-1 text-2xs">
                    Warning: Removal terminates all permissions and data associations for this workspace seat.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-2.5 pt-2 border-t border-border/70">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setConfirmAction(null)}
                  disabled={isActionExecuting}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant={confirmAction.type.includes('remove') ? 'destructive' : 'default'}
                  onClick={handleExecuteConfirmAction}
                  disabled={isActionExecuting}
                  data-testid="modal-confirm-action"
                >
                  {isActionExecuting && <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />}
                  {confirmAction.type.includes('remove')
                    ? 'Confirm Removal'
                    : confirmAction.type.includes('suspend')
                    ? 'Confirm Suspension'
                    : 'Confirm Restoration'}
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Invite Member Modal */}
      <AnimatePresence>
        {isInviteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xs p-4">
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="w-full max-w-lg bg-card border border-border rounded-xl shadow-xl p-6 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-3">
                <div className="flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-primary" />
                  <h3 className="font-semibold text-sm text-foreground">Invite New Team Member</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {inviteSuccess ? (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/25 rounded-lg flex items-center gap-2.5 text-emerald-500 text-xs font-mono">
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{inviteSuccess}</span>
                </div>
              ) : (
                <form onSubmit={handleSendInvite} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="inviteEmail" className="text-xs font-semibold">
                      Recipient Email
                    </Label>
                    <Input
                      id="inviteEmail"
                      type="email"
                      required
                      placeholder="colleague@organization.com"
                      value={inviteEmail}
                      onChange={e => setInviteEmail(e.target.value)}
                      className="h-9 text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="inviteRole" className="text-xs font-semibold">
                      Assigned Workspace Role
                    </Label>
                    <select
                      id="inviteRole"
                      value={inviteRole}
                      onChange={e => setInviteRole(e.target.value)}
                      className="w-full h-9 px-3 text-xs bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer font-mono"
                    >
                      {isCurrentUserOwner && <option value="ADMIN">ADMIN — Workspace Management & Quota Authority</option>}
                      <option value="MEMBER">MEMBER — Retrieval, Generation, and Document Ingestion</option>
                      <option value="VIEWER">VIEWER — Read-Only Observability & History</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="inviteMessage" className="text-xs font-semibold">
                      Custom Message (Optional)
                    </Label>
                    <textarea
                      id="inviteMessage"
                      rows={3}
                      placeholder="Welcome to our Veritas-RAG workspace..."
                      value={inviteMessage}
                      onChange={e => setInviteMessage(e.target.value)}
                      className="w-full p-2.5 text-xs bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                    />
                  </div>

                  <div className="flex justify-end gap-2.5 pt-3 border-t border-border/80">
                    <Button type="button" variant="outline" size="sm" onClick={() => setIsInviteModalOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="submit" size="sm" disabled={sendingInvite}>
                      {sendingInvite && <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />}
                      Send Invitation
                    </Button>
                  </div>
                </form>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default WorkspaceMembersPage
