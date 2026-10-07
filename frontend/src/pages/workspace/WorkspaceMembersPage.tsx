import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { useMemberStore } from '@/stores/memberStore'
import { invitationService } from '@/services/invitationService'
import { workspaceService } from '@/services/workspaceService'
import { accessRequestService, AccessRequestData } from '@/services/accessRequestService'
import type { WorkspaceInvitation } from '@/types/workspaceInvitation'
import type { WorkspaceJoinAccessResponse } from '@/types'
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
  Copy,
  Check,
  ExternalLink,
  KeyRound,
  LogOut,
  Inbox,
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
  type:
    | 'suspend'
    | 'restore'
    | 'remove'
    | 'bulk_suspend'
    | 'bulk_restore'
    | 'bulk_remove'
    | 'revoke_invite'
    | 'leave'
    | 'reject_request'
  memberId?: string
  memberName?: string
  memberCount?: number
  invitationId?: string
  invitationEmail?: string
  requestId?: string
  requesterName?: string
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
    description: 'Can invite members, manage non-owner roles, configure quotas, and review inbound access requests.',
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

  // Tabs: members | invitations | requests
  const [activeTab, setActiveTab] = useState<'members' | 'invitations' | 'requests'>('members')
  const [search, setSearch] = useState<string>('')
  const [roleFilter, setRoleFilter] = useState<string>('')
  const [selectedMembers, setSelectedMembers] = useState<string[]>([])
  const [showRoleGuide, setShowRoleGuide] = useState<boolean>(false)

  // Confirmation Modal state
  const [confirmAction, setConfirmAction] = useState<ConfirmActionState | null>(null)
  const [isActionExecuting, setIsActionExecuting] = useState<boolean>(false)
  const [rejectionReasonInput, setRejectionReasonInput] = useState<string>('')

  // Invite modal state
  const [isInviteModalOpen, setIsInviteModalOpen] = useState<boolean>(false)
  const [inviteModalTab, setInviteModalTab] = useState<'email' | 'credentials'>('email')
  const [inviteEmail, setInviteEmail] = useState<string>('')
  const [inviteRole, setInviteRole] = useState<string>('MEMBER')
  const [inviteMessage, setInviteMessage] = useState<string>('')
  const [sendingInvite, setSendingInvite] = useState<boolean>(false)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  // Active Join Credentials state
  const [joinAccess, setJoinAccess] = useState<WorkspaceJoinAccessResponse | null>(null)
  const [loadingJoinAccess, setLoadingJoinAccess] = useState<boolean>(false)
  const [copiedCode, setCopiedCode] = useState<boolean>(false)
  const [copiedLink, setCopiedLink] = useState<boolean>(false)

  // Invitations list state
  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([])
  const [loadingInvitations, setLoadingInvitations] = useState<boolean>(false)

  // Access Requests state
  const [accessRequests, setAccessRequests] = useState<AccessRequestData[]>([])
  const [loadingAccessRequests, setLoadingAccessRequests] = useState<boolean>(false)
  const [isRequestElevationModalOpen, setIsRequestElevationModalOpen] = useState<boolean>(false)
  const [elevationReason, setElevationReason] = useState<string>('')
  const [submittingElevation, setSubmittingElevation] = useState<boolean>(false)
  const [elevationSuccess, setElevationSuccess] = useState<string | null>(null)

  const isCurrentUserOwner = String(user?.role || '').trim().toUpperCase() === 'OWNER'
  const isCurrentUserAdmin = ['OWNER', 'ADMIN'].includes(String(user?.role || '').trim().toUpperCase())

  // Authoritative Join Credentials Fetcher
  const loadJoinCredentials = useCallback(async () => {
    if (!workspaceId) return
    try {
      setLoadingJoinAccess(true)
      const res = await workspaceService.getJoinCodeAccess(workspaceId)
      setJoinAccess(res)
    } catch (err) {
      console.error('Failed to load authoritative join credentials', err)
    } finally {
      setLoadingJoinAccess(false)
    }
  }, [workspaceId])

  // Load Invitations (Query-time active non-expired)
  const loadInvitations = useCallback(async () => {
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
  }, [workspaceId])

  // Load Access Requests
  const loadAccessRequests = useCallback(async () => {
    if (!workspaceId || !isCurrentUserAdmin) return
    try {
      setLoadingAccessRequests(true)
      const res = await accessRequestService.listRequests(workspaceId)
      setAccessRequests(res.items)
    } catch (err) {
      console.error('Failed to load access requests', err)
    } finally {
      setLoadingAccessRequests(false)
    }
  }, [workspaceId, isCurrentUserAdmin])

  // Mount-time synchronous population of all counters
  useEffect(() => {
    if (workspaceId) {
      fetchMembers(workspaceId, { search, role: roleFilter || undefined })
      loadInvitations()
      if (isCurrentUserAdmin) {
        loadAccessRequests()
      }
    }
  }, [workspaceId, search, roleFilter, fetchMembers, loadInvitations, loadAccessRequests, isCurrentUserAdmin])

  // Handle opening credentials tab
  useEffect(() => {
    if (isInviteModalOpen && inviteModalTab === 'credentials') {
      loadJoinCredentials()
    }
  }, [isInviteModalOpen, inviteModalTab, loadJoinCredentials])

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
      await loadInvitations()
      setTimeout(() => {
        setIsInviteModalOpen(false)
        setInviteSuccess(null)
      }, 1500)
    } catch (err: any) {
      console.error('Failed to send invitation', err)
    } finally {
      setSendingInvite(false)
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

  const handleCopyCode = () => {
    if (!joinAccess?.join_code) return
    navigator.clipboard.writeText(joinAccess.join_code)
    setCopiedCode(true)
    setTimeout(() => setCopiedCode(false), 2000)
  }

  const handleCopyLink = () => {
    if (!joinAccess?.join_link) return
    navigator.clipboard.writeText(joinAccess.join_link)
    setCopiedLink(true)
    setTimeout(() => setCopiedLink(false), 2000)
  }

  const handleSubmitElevationRequest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!workspaceId) return
    try {
      setSubmittingElevation(true)
      await accessRequestService.submitRequest(workspaceId, {
        request_type: 'ROLE_ELEVATION',
        requested_role: 'ADMIN',
        reason: elevationReason || undefined,
      })
      setElevationSuccess('Your request for administrator privileges has been submitted to workspace owners.')
      setElevationReason('')
      setTimeout(() => {
        setIsRequestElevationModalOpen(false)
        setElevationSuccess(null)
      }, 2000)
    } catch (err: any) {
      console.error('Failed to submit elevation request', err)
    } finally {
      setSubmittingElevation(false)
    }
  }

  const handleApproveRequest = async (requestId: string) => {
    if (!workspaceId) return
    try {
      await accessRequestService.approveRequest(workspaceId, requestId)
      await loadAccessRequests()
      await fetchMembers(workspaceId, { search, role: roleFilter || undefined })
    } catch (err) {
      console.error('Failed to approve request', err)
    }
  }

  const handleToggleSelectAll = () => {
    const selectable = members.filter(m => m.role !== 'OWNER' && m.user_id !== user?.id).map(m => m.id)
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
      } else if (confirmAction.type === 'leave' && confirmAction.memberId) {
        await removeMember(workspaceId, confirmAction.memberId)
        window.location.href = '/dashboard'
      } else if (confirmAction.type === 'revoke_invite' && confirmAction.invitationId) {
        await invitationService.revokeInvitation(workspaceId, confirmAction.invitationId)
        await loadInvitations()
      } else if (confirmAction.type === 'reject_request' && confirmAction.requestId) {
        await accessRequestService.rejectRequest(workspaceId, confirmAction.requestId, {
          rejection_reason: rejectionReasonInput || undefined,
        })
        setRejectionReasonInput('')
        await loadAccessRequests()
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

  const pendingRequestsCount = useMemo(
    () => accessRequests.filter(r => r.status === 'PENDING').length,
    [accessRequests]
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
            {!isCurrentUserAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsRequestElevationModalOpen(true)}
                className="flex items-center gap-1.5 text-xs text-indigo-400 border-indigo-500/30 hover:bg-indigo-500/10"
              >
                <Shield className="h-3.5 w-3.5" />
                <span>Request to Admin</span>
              </Button>
            )}
            {isCurrentUserAdmin && (
              <Button onClick={() => setIsInviteModalOpen(true)} className="flex items-center gap-2 shadow-xs" size="sm">
                <UserPlus className="h-4 w-4" />
                <span>Invite Team Member</span>
              </Button>
            )}
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

      {/* Overview Stat Cards (4 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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

        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between bg-card hover:border-border transition-colors">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Access Requests
            </span>
            <div className="text-2xl font-bold text-foreground mt-1 font-mono">{pendingRequestsCount}</div>
          </div>
          <div className="p-2.5 bg-sky-500/10 rounded-lg text-sky-400">
            <Inbox className="h-5 w-5" />
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
        {isCurrentUserAdmin && (
          <button
            onClick={() => setActiveTab('requests')}
            className={cn(
              'pb-3 text-sm font-medium transition-all border-b-2 flex items-center gap-2 cursor-pointer',
              activeTab === 'requests'
                ? 'border-primary text-primary font-semibold'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <Inbox className="h-4 w-4" />
            <span>Access Requests ({pendingRequestsCount})</span>
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30 flex items-center gap-3 text-destructive text-sm animate-in fade-in">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={clearError} className="text-xs hover:underline font-mono cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* TAB 1: MEMBERS */}
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

            {selectedMembers.length > 0 && isCurrentUserAdmin && (
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
          <div className="rounded-xl border border-border/80 bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border/80 bg-muted/40 text-2xs uppercase tracking-wider font-semibold text-muted-foreground font-mono">
                  <th scope="col" className="p-3.5 w-10">
                    {isCurrentUserAdmin && (
                      <input
                        type="checkbox"
                        checked={
                          selectedMembers.length > 0 &&
                          selectedMembers.length === members.filter(m => m.role !== 'OWNER' && m.user_id !== user?.id).length
                        }
                        onChange={handleToggleSelectAll}
                        className="rounded border-input bg-background text-primary focus:ring-primary cursor-pointer"
                        title="Select all actionable members"
                      />
                    )}
                  </th>
                  <th scope="col" className="p-3.5">Member Identity</th>
                  <th scope="col" className="p-3.5">Assigned Role</th>
                  <th scope="col" className="p-3.5">Seat Status</th>
                  <th scope="col" className="p-3.5">Member Since</th>
                  <th scope="col" className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-xs">
                {isLoading && members.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                        <span className="font-mono text-2xs">Loading active seat roster...</span>
                      </div>
                    </td>
                  </tr>
                ) : members.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground">
                      <div className="text-sm font-medium text-foreground">No members found matching filters</div>
                      <p className="text-xs text-muted-foreground mt-1">Try resetting search keywords or role filters.</p>
                      {(search || roleFilter) && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSearch('')
                            setRoleFilter('')
                          }}
                          className="mt-3 text-xs"
                        >
                          Clear Filters
                        </Button>
                      )}
                    </td>
                  </tr>
                ) : (
                  members.map(member => {
                    const isOwner = member.role === 'OWNER'
                    const isSuspended = member.status === 'SUSPENDED'
                    const displayName = member.user?.display_name || member.user?.username || ''
                    const email = member.user?.email || member.user_id
                    const isCurrentUser = Boolean(
                      member.user_id === user?.id ||
                      (user?.email && member.user?.email === user?.email)
                    )

                    return (
                      <tr
                        key={member.id}
                        className={cn(
                          'hover:bg-muted/30 transition-colors',
                          isOwner && 'bg-amber-500/[0.02]',
                          isSuspended && 'opacity-70 bg-muted/20',
                          isCurrentUser && 'bg-primary/[0.03]'
                        )}
                      >
                        <td className="p-3.5">
                          {!isOwner && !isCurrentUser && isCurrentUserAdmin ? (
                            <input
                              type="checkbox"
                              checked={selectedMembers.includes(member.id)}
                              onChange={() => handleToggleSelect(member.id)}
                              className="rounded border-input bg-background text-primary focus:ring-primary cursor-pointer"
                            />
                          ) : isOwner ? (
                            <div className="h-4 w-4 flex items-center justify-center text-amber-500/60" title="Owner cannot be bulk-managed">
                              <Crown className="h-3 w-3" />
                            </div>
                          ) : (
                            <div className="h-4 w-4" />
                          )}
                        </td>
                        <td className="p-3.5">
                          <div className="flex items-center gap-3">
                            <div
                              className={cn(
                                'h-8 w-8 rounded-full border flex items-center justify-center text-xs font-bold shrink-0',
                                isOwner
                                  ? 'bg-amber-500/15 border-amber-500/30 text-amber-500'
                                  : isCurrentUser
                                  ? 'bg-primary/20 border-primary/40 text-primary'
                                  : 'bg-primary/10 border-primary/20 text-primary'
                              )}
                            >
                              {email?.[0]?.toUpperCase() || 'U'}
                            </div>
                            <div className="truncate max-w-[260px]">
                              <div className="font-medium text-foreground text-sm flex items-center gap-1.5 truncate">
                                <span>{displayName || email}</span>
                                {isCurrentUser && (
                                  <span className="px-1.5 py-0.2 rounded text-3xs font-mono font-bold bg-primary/10 text-primary border border-primary/25">
                                    YOU
                                  </span>
                                )}
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
                          {isOwner || isCurrentUser || !isCurrentUserAdmin ? (
                            getRoleBadge(member.role)
                          ) : (
                            <select
                              value={member.role}
                              onChange={e => workspaceId && updateRole(workspaceId, member.id, e.target.value)}
                              className="border border-border/80 rounded-md px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary bg-background cursor-pointer"
                              title="Update member role"
                            >
                              {isCurrentUserOwner && <option value="ADMIN">ADMIN</option>}
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
                            <span className={cn('h-1.5 w-1.5 rounded-full', member.status === 'ACTIVE' ? 'bg-emerald-500' : 'bg-amber-500')} />
                            {member.status}
                          </span>
                        </td>
                        <td className="p-3.5 text-xs text-muted-foreground font-mono">
                          {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'N/A'}
                        </td>
                        <td className="p-3.5 text-right space-x-1 whitespace-nowrap">
                          {isCurrentUser && !isOwner ? (
                            <button
                              onClick={() =>
                                setConfirmAction({
                                  type: 'leave',
                                  memberId: member.id,
                                  memberName: displayName || email,
                                })
                              }
                              title="Leave this workspace"
                              className="inline-flex items-center gap-1 px-2 py-1 rounded text-2xs font-mono text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                            >
                              <LogOut className="h-3.5 w-3.5" />
                              <span>Leave</span>
                            </button>
                          ) : !isOwner && !isCurrentUser && isCurrentUserAdmin ? (
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
      )}

      {/* TAB 2: INVITATIONS */}
      {activeTab === 'invitations' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border/80 bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border/80 bg-muted/40 text-2xs uppercase tracking-wider font-semibold text-muted-foreground font-mono">
                  <th scope="col" className="p-3.5">Recipient Email</th>
                  <th scope="col" className="p-3.5">Invited Role</th>
                  <th scope="col" className="p-3.5">Status</th>
                  <th scope="col" className="p-3.5">Expires At</th>
                  <th scope="col" className="p-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-xs">
                {loadingInvitations ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-muted-foreground">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                        <span className="font-mono text-2xs">Fetching pending invitations...</span>
                      </div>
                    </td>
                  </tr>
                ) : invitations.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-muted-foreground">
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
                      <td className="p-3.5">{getRoleBadge(inv.role)}</td>
                      <td className="p-3.5">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold font-mono border bg-amber-500/10 text-amber-500 border-amber-500/20">
                          <Clock className="h-3 w-3" />
                          {inv.status}
                        </span>
                      </td>
                      <td className="p-3.5 text-xs text-muted-foreground font-mono">
                        {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="p-3.5 text-right space-x-1.5 whitespace-nowrap">
                        {inv.status === 'PENDING' && isCurrentUserAdmin && (
                          <>
                            <button
                              onClick={() => handleResendInvitation(inv.id)}
                              title="Resend Invitation Email"
                              className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-muted transition-colors cursor-pointer"
                            >
                              <RotateCw className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() =>
                                setConfirmAction({
                                  type: 'revoke_invite',
                                  invitationId: inv.id,
                                  invitationEmail: inv.email,
                                })
                              }
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

      {/* TAB 3: ACCESS REQUESTS (Admin/Owner) */}
      {activeTab === 'requests' && isCurrentUserAdmin && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border/80 bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border/80 bg-muted/40 text-2xs uppercase tracking-wider font-semibold text-muted-foreground font-mono">
                  <th scope="col" className="p-3.5">Applicant Identity</th>
                  <th scope="col" className="p-3.5">Request Type</th>
                  <th scope="col" className="p-3.5">Role Elevation</th>
                  <th scope="col" className="p-3.5">Reason / Note</th>
                  <th scope="col" className="p-3.5">Status</th>
                  <th scope="col" className="p-3.5">Submitted</th>
                  <th scope="col" className="p-3.5 text-right">Review Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 text-xs">
                {loadingAccessRequests ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-muted-foreground">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                        <span className="font-mono text-2xs">Loading access requests...</span>
                      </div>
                    </td>
                  </tr>
                ) : accessRequests.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8 text-center text-muted-foreground">
                      <div className="text-sm font-medium text-foreground">No access requests pending review</div>
                      <p className="text-xs text-muted-foreground mt-1">Incoming member elevation requests and join approvals appear here.</p>
                    </td>
                  </tr>
                ) : (
                  accessRequests.map(req => {
                    const requesterName = req.user_display_name || req.user_email || req.user_id
                    const isPending = req.status === 'PENDING'

                    return (
                      <tr key={req.id} className="hover:bg-muted/30 transition-colors">
                        <td className="p-3.5">
                          <div className="font-medium text-foreground text-sm font-mono truncate max-w-[200px]">
                            {requesterName}
                          </div>
                          {req.user_email && req.user_display_name && (
                            <div className="text-2xs text-muted-foreground font-mono">{req.user_email}</div>
                          )}
                        </td>
                        <td className="p-3.5 font-mono text-2xs">
                          {req.request_type === 'ROLE_ELEVATION' ? (
                            <span className="inline-flex items-center gap-1 text-indigo-400">
                              <Shield className="h-3 w-3" />
                              Role Elevation
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-sky-400">
                              <KeyRound className="h-3 w-3" />
                              Join Approval
                            </span>
                          )}
                        </td>
                        <td className="p-3.5">
                          <div className="flex items-center gap-1.5 font-mono text-2xs">
                            <span className="text-muted-foreground">{req.current_role || 'Prospect'}</span>
                            <span className="text-muted-foreground">→</span>
                            <span className="font-semibold text-primary">{req.requested_role}</span>
                          </div>
                        </td>
                        <td className="p-3.5 max-w-[240px] truncate text-muted-foreground text-2xs" title={req.reason || 'No message'}>
                          {req.reason || '—'}
                        </td>
                        <td className="p-3.5">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-2xs font-semibold font-mono border',
                              req.status === 'PENDING'
                                ? 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                                : req.status === 'APPROVED'
                                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                : 'bg-zinc-800 text-zinc-400 border-zinc-700'
                            )}
                          >
                            {req.status}
                          </span>
                        </td>
                        <td className="p-3.5 text-xs text-muted-foreground font-mono">
                          {new Date(req.created_at).toLocaleDateString()}
                        </td>
                        <td className="p-3.5 text-right space-x-2 whitespace-nowrap">
                          {isPending && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleApproveRequest(req.id)}
                                className="h-7 text-2xs text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10 cursor-pointer"
                              >
                                Approve
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  setConfirmAction({
                                    type: 'reject_request',
                                    requestId: req.id,
                                    requesterName,
                                  })
                                }
                                className="h-7 text-2xs text-destructive border-destructive/30 hover:bg-destructive/10 cursor-pointer"
                              >
                                Reject
                              </Button>
                            </>
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
      )}

      {/* Confirmation Modals */}
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
                    confirmAction.type.includes('remove') || confirmAction.type === 'revoke_invite' || confirmAction.type === 'leave' || confirmAction.type === 'reject_request'
                      ? 'bg-destructive/10 text-destructive'
                      : confirmAction.type.includes('suspend')
                      ? 'bg-amber-500/10 text-amber-500'
                      : 'bg-emerald-500/10 text-emerald-500'
                  )}
                >
                  {confirmAction.type.includes('remove') ? (
                    <Trash2 className="h-5 w-5" />
                  ) : confirmAction.type === 'revoke_invite' ? (
                    <Ban className="h-5 w-5" />
                  ) : confirmAction.type === 'leave' ? (
                    <LogOut className="h-5 w-5" />
                  ) : confirmAction.type.includes('suspend') ? (
                    <UserX className="h-5 w-5" />
                  ) : (
                    <UserCheck className="h-5 w-5" />
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-foreground">
                    {confirmAction.type === 'leave'
                      ? 'Leave This Workspace'
                      : confirmAction.type === 'revoke_invite'
                      ? 'Revoke Invitation'
                      : confirmAction.type === 'reject_request'
                      ? 'Reject Access Request'
                      : confirmAction.type.includes('remove')
                      ? 'Confirm Member Removal'
                      : confirmAction.type.includes('suspend')
                      ? 'Confirm Member Suspension'
                      : 'Confirm Action'}
                  </h3>
                  <p className="text-2xs text-muted-foreground font-mono mt-0.5">Authoritative Lifecycle Transition</p>
                </div>
              </div>

              <div className="p-3 bg-muted/30 rounded-lg border border-border/60 text-xs text-muted-foreground space-y-2">
                {confirmAction.memberName && (
                  <p>
                    Target Member: <span className="font-semibold text-foreground">{confirmAction.memberName}</span>
                  </p>
                )}
                {confirmAction.invitationEmail && (
                  <p>
                    Target Email: <span className="font-semibold text-foreground">{confirmAction.invitationEmail}</span>
                  </p>
                )}
                {confirmAction.requesterName && (
                  <p>
                    Requester: <span className="font-semibold text-foreground">{confirmAction.requesterName}</span>
                  </p>
                )}
                {confirmAction.type === 'reject_request' && (
                  <div className="space-y-1.5 pt-1">
                    <Label htmlFor="rejectionReason" className="text-2xs font-semibold text-foreground">
                      Rejection Rationale (Optional)
                    </Label>
                    <Input
                      id="rejectionReason"
                      placeholder="Explain reason for administrative record..."
                      value={rejectionReasonInput}
                      onChange={e => setRejectionReasonInput(e.target.value)}
                      className="h-8 text-xs bg-background"
                    />
                  </div>
                )}
                {confirmAction.type === 'leave' && (
                  <p className="text-amber-500/90 text-2xs">
                    You will immediately lose access to this workspace. You will need an invite or join code to return.
                  </p>
                )}
                {confirmAction.type === 'revoke_invite' && (
                  <p className="text-destructive/90 text-2xs">
                    The cryptographic invitation token will be immediately invalidated and cannot be redeemed.
                  </p>
                )}
                {confirmAction.type.includes('suspend') && (
                  <p className="text-amber-500/90 text-2xs">
                    Security note: Suspending immediately revokes active JWT tokens in Redis. The user will be disconnected.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-2.5 pt-2 border-t border-border/70">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setConfirmAction(null)
                    setRejectionReasonInput('')
                  }}
                  disabled={isActionExecuting}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant={
                    confirmAction.type.includes('remove') ||
                    confirmAction.type === 'revoke_invite' ||
                    confirmAction.type === 'leave' ||
                    confirmAction.type === 'reject_request'
                      ? 'destructive'
                      : 'default'
                  }
                  onClick={handleExecuteConfirmAction}
                  disabled={isActionExecuting}
                >
                  {isActionExecuting && <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />}
                  Confirm
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* DUAL-TAB INVITE MEMBER MODAL */}
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
                  <h3 className="font-semibold text-sm text-foreground">Invite Team Member</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Sub-Tabs: Invite by Email vs Active Join Credentials */}
              <div className="flex border-b border-border gap-4">
                <button
                  type="button"
                  onClick={() => setInviteModalTab('email')}
                  className={cn(
                    'pb-2 text-xs font-medium transition-all border-b-2 flex items-center gap-1.5 cursor-pointer',
                    inviteModalTab === 'email'
                      ? 'border-primary text-primary font-semibold'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  <Mail className="h-3.5 w-3.5" />
                  <span>Invite by Email</span>
                </button>
                <button
                  type="button"
                  onClick={() => setInviteModalTab('credentials')}
                  className={cn(
                    'pb-2 text-xs font-medium transition-all border-b-2 flex items-center gap-1.5 cursor-pointer',
                    inviteModalTab === 'credentials'
                      ? 'border-primary text-primary font-semibold'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  <KeyRound className="h-3.5 w-3.5" />
                  <span>Active Join Credentials</span>
                </button>
              </div>

              {/* TAB 1: INVITE BY EMAIL */}
              {inviteModalTab === 'email' && (
                <>
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
                </>
              )}

              {/* TAB 2: ACTIVE JOIN CREDENTIALS */}
              {inviteModalTab === 'credentials' && (
                <div className="space-y-4">
                  {loadingJoinAccess ? (
                    <div className="p-8 text-center text-muted-foreground flex flex-col items-center justify-center gap-2">
                      <Loader2 className="h-6 w-6 animate-spin text-primary" />
                      <span className="font-mono text-2xs">Fetching authoritative join credentials...</span>
                    </div>
                  ) : !joinAccess?.has_active_code ? (
                    <div className="p-6 bg-muted/20 border border-border/60 rounded-xl text-center space-y-2">
                      <AlertTriangle className="h-6 w-6 text-amber-500 mx-auto" />
                      <div className="text-sm font-semibold text-foreground">No Active Join Code Configured</div>
                      <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                        Enable or generate a Join Code in Workspace Settings to permit self-service team joining.
                      </p>
                      <Link to={`/settings/workspace`}>
                        <Button variant="outline" size="sm" className="mt-2 text-xs">
                          Configure Join Codes
                          <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
                        </Button>
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {/* Active Code Container */}
                      <div className="p-4 bg-muted/30 border border-border/80 rounded-xl space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                            Active Join Code
                          </span>
                          <button
                            type="button"
                            onClick={loadJoinCredentials}
                            className="text-2xs font-mono text-muted-foreground hover:text-foreground flex items-center gap-1 cursor-pointer"
                            title="Refresh Authoritative State"
                          >
                            <RotateCw className="h-3 w-3" />
                            <span>Refresh</span>
                          </button>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 font-mono text-lg font-bold tracking-widest text-primary bg-background/80 px-3 py-2 rounded-lg border border-border">
                            {joinAccess.join_code}
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleCopyCode}
                            className="h-10 px-3 cursor-pointer"
                          >
                            {copiedCode ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
                            <span className="ml-1.5 text-xs">{copiedCode ? 'Copied' : 'Copy'}</span>
                          </Button>
                        </div>

                        {/* Join Link */}
                        {joinAccess.join_link && (
                          <div className="space-y-1.5 pt-1">
                            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                              Active Join Link
                            </span>
                            <div className="flex items-center gap-2">
                              <Input
                                readOnly
                                value={joinAccess.join_link}
                                className="h-8 text-2xs font-mono bg-background/80 text-muted-foreground"
                              />
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={handleCopyLink}
                                className="h-8 px-2.5 cursor-pointer shrink-0"
                              >
                                {copiedLink ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                              </Button>
                            </div>
                          </div>
                        )}

                        {/* Metadata summary */}
                        <div className="flex items-center justify-between text-2xs font-mono text-muted-foreground pt-1 border-t border-border/50">
                          <span>Default Role: <strong className="text-foreground">{joinAccess.default_role || 'MEMBER'}</strong></span>
                          <span>
                            {joinAccess.expires_at ? (
                              `Expires: ${new Date(joinAccess.expires_at).toLocaleDateString()}`
                            ) : (
                              'No expiration set'
                            )}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-2xs text-muted-foreground pt-1">
                        <span className="font-mono">Server Authoritative Sync</span>
                        <Link
                          to={`/settings/workspace`}
                          className="hover:underline flex items-center gap-1 text-primary font-mono"
                        >
                          <span>Manage Policy in Settings</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>

                      <div className="flex justify-end pt-2 border-t border-border/80">
                        <Button type="button" variant="outline" size="sm" onClick={() => setIsInviteModalOpen(false)}>
                          Close
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* REQUEST TO ADMIN MODAL (For Member / Viewer) */}
      <AnimatePresence>
        {isRequestElevationModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xs p-4">
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="w-full max-w-md bg-card border border-border rounded-xl shadow-xl p-6 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-border/80 pb-3">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-indigo-400" />
                  <h3 className="font-semibold text-sm text-foreground">Request Administrator Privileges</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsRequestElevationModalOpen(false)}
                  className="text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {elevationSuccess ? (
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/25 rounded-lg flex items-center gap-2.5 text-emerald-500 text-xs font-mono">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{elevationSuccess}</span>
                </div>
              ) : (
                <form onSubmit={handleSubmitElevationRequest} className="space-y-4">
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Submitting this request alerts workspace owners to review elevating your seat to Administrator,
                    granting permission to manage members and configure quotas.
                  </p>

                  <div className="space-y-1.5">
                    <Label htmlFor="elevationReason" className="text-xs font-semibold">
                      Reason for Request (Optional)
                    </Label>
                    <textarea
                      id="elevationReason"
                      rows={3}
                      placeholder="e.g. Managing ingestion for the engineering team..."
                      value={elevationReason}
                      onChange={e => setElevationReason(e.target.value)}
                      className="w-full p-2.5 text-xs bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                    />
                  </div>

                  <div className="flex justify-end gap-2.5 pt-2 border-t border-border/80">
                    <Button type="button" variant="outline" size="sm" onClick={() => setIsRequestElevationModalOpen(false)}>
                      Cancel
                    </Button>
                    <Button type="submit" size="sm" disabled={submittingElevation}>
                      {submittingElevation && <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />}
                      Submit Request
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
