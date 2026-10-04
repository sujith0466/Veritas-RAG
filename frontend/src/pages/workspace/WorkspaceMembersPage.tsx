import React, { useEffect, useState } from 'react'
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
  RefreshCw,
  Mail,
  Send,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  UserCheck2,
  Clock,
  X,
} from 'lucide-react'

import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { AdminPageHeader } from '@/components/admin/AdminPageHeader'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { Label } from '@/components/common/Label'
import { Card } from '@/components/common/Card'
import { cn } from '@/utils/cn'

export const WorkspaceMembersPage: React.FC = () => {
  const { workspaceId: paramWorkspaceId } = useParams<{ workspaceId: string }>()
  const user = useAuthStore(s => s.user)
  const currentWorkspace = useWorkspaceStore(s => s.currentWorkspace)
  const shouldReduceMotion = useReducedMotion()

  const workspaceId = paramWorkspaceId || currentWorkspace?.id || user?.tenant_id || user?.workspace_name
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
  const [isInviteModalOpen, setIsInviteModalOpen] = useState<boolean>(false)
  const [inviteEmail, setInviteEmail] = useState<string>('')
  const [inviteRole, setInviteRole] = useState<string>('MEMBER')
  const [inviteMessage, setInviteMessage] = useState<string>('')
  const [sendingInvite, setSendingInvite] = useState<boolean>(false)
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([])
  const [loadingInvitations, setLoadingInvitations] = useState<boolean>(false)

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

  const handleToggleSelectAll = () => {
    if (selectedMembers.length === members.length && members.length > 0) {
      setSelectedMembers([])
    } else {
      setSelectedMembers(members.map(m => m.id))
    }
  }

  const handleToggleSelect = (id: string) => {
    setSelectedMembers(prev => (prev.includes(id) ? prev.filter(mid => mid !== id) : [...prev, id]))
  }

  const handleBulkAction = async (action: 'suspend' | 'restore' | 'remove') => {
    if (!workspaceId || selectedMembers.length === 0) return
    if (confirm(`Are you sure you want to ${action} ${selectedMembers.length} selected member(s)?`)) {
      await bulkManage(workspaceId, { action, member_ids: selectedMembers })
      setSelectedMembers([])
    }
  }

  const ownersAndAdminsCount = members.filter(m => m.role === 'OWNER' || m.role === 'ADMIN').length

  const getRoleBadgeClass = (role: string) => {
    switch (role?.toUpperCase()) {
      case 'OWNER':
        return 'bg-primary/10 text-primary border-primary/25'
      case 'ADMIN':
        return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/25'
      case 'MEMBER':
        return 'bg-slate-500/10 text-slate-300 border-slate-500/25'
      case 'VIEWER':
      default:
        return 'bg-muted text-muted-foreground border-border/50'
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
          <Button onClick={() => setIsInviteModalOpen(true)} className="flex items-center gap-2 shadow-xs">
            <UserPlus className="h-4 w-4" />
            <span>Invite Team Member</span>
          </Button>
        }
      />

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Total Active Members
            </span>
            <div className="text-2xl font-bold text-foreground mt-1">{total}</div>
          </div>
          <div className="p-2.5 bg-primary/10 rounded-lg text-primary">
            <Users className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Administrators & Owners
            </span>
            <div className="text-2xl font-bold text-foreground mt-1">{ownersAndAdminsCount}</div>
          </div>
          <div className="p-2.5 bg-indigo-500/10 rounded-lg text-indigo-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 border border-border/80 shadow-xs flex items-center justify-between">
          <div>
            <span className="text-2xs font-semibold text-muted-foreground uppercase tracking-wider font-mono">
              Pending Invitations
            </span>
            <div className="text-2xl font-bold text-foreground mt-1">{invitations.length}</div>
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
            'pb-3 text-sm font-medium transition-all border-b-2 flex items-center gap-2',
            activeTab === 'members'
              ? 'border-primary text-primary font-semibold'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <UserCheck2 className="h-4 w-4" />
          <span>Active Members ({total})</span>
        </button>
        <button
          onClick={() => setActiveTab('invitations')}
          className={cn(
            'pb-3 text-sm font-medium transition-all border-b-2 flex items-center gap-2',
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
          <button onClick={clearError} className="text-xs hover:underline font-mono">Dismiss</button>
        </div>
      )}

      {activeTab === 'members' && (
        <div className="space-y-4">
          {/* Filters & Bulk Actions Toolbar */}
          <div className="flex flex-col sm:flex-row justify-between gap-3 items-stretch sm:items-center bg-card p-3 rounded-lg border border-border shadow-xs">
            <div className="flex flex-1 items-center gap-3">
              <div className="relative flex-1">
                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search members by email or name..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 h-9 text-xs bg-background/80"
                />
              </div>
              <select
                value={roleFilter}
                onChange={e => setRoleFilter(e.target.value)}
                className="h-9 px-3 bg-background border border-input rounded-md text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
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
                  onClick={() => handleBulkAction('suspend')}
                  className="h-7 text-2xs text-amber-500 border-amber-500/30 hover:bg-amber-500/10"
                >
                  Suspend
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkAction('restore')}
                  className="h-7 text-2xs text-emerald-500 border-emerald-500/30 hover:bg-emerald-500/10"
                >
                  Restore
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleBulkAction('remove')}
                  className="h-7 text-2xs text-destructive border-destructive/30 hover:bg-destructive/10"
                >
                  Remove
                </Button>
              </div>
            )}
          </div>

          {/* Members Table */}
          <div className="bg-card border border-border rounded-lg overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-foreground">
                <thead className="bg-muted/40 text-2xs uppercase text-muted-foreground font-mono tracking-wider border-b border-border">
                  <tr>
                    <th className="p-3.5 w-10">
                      <input
                        type="checkbox"
                        checked={selectedMembers.length > 0 && selectedMembers.length === members.length}
                        onChange={handleToggleSelectAll}
                        className="rounded border-input bg-background text-primary focus:ring-primary"
                      />
                    </th>
                    <th className="p-3.5 font-semibold">User</th>
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
                    members.map(member => (
                      <tr key={member.id} className="hover:bg-muted/30 transition-colors">
                        <td className="p-3.5">
                          <input
                            type="checkbox"
                            checked={selectedMembers.includes(member.id)}
                            onChange={() => handleToggleSelect(member.id)}
                            className="rounded border-input bg-background text-primary focus:ring-primary"
                          />
                        </td>
                        <td className="p-3.5">
                          <div className="flex items-center gap-3">
                            <div className="h-8 w-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-xs text-primary font-bold">
                              {member.user?.email?.[0]?.toUpperCase() || 'U'}
                            </div>
                            <div>
                              <div className="font-medium text-foreground text-sm">
                                {member.user?.email || member.user_id}
                              </div>
                              {member.user?.username && (
                                <div className="text-2xs text-muted-foreground font-mono">@{member.user.username}</div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="p-3.5">
                          <select
                            value={member.role}
                            onChange={e => workspaceId && updateRole(workspaceId, member.id, e.target.value)}
                            className={cn(
                              'border rounded-md px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary bg-background',
                              getRoleBadgeClass(member.role)
                            )}
                          >
                            <option value="OWNER">OWNER</option>
                            <option value="ADMIN">ADMIN</option>
                            <option value="MEMBER">MEMBER</option>
                            <option value="VIEWER">VIEWER</option>
                          </select>
                        </td>
                        <td className="p-3.5">
                          <span
                            className={cn(
                              'px-2 py-0.5 rounded-full text-2xs font-semibold font-mono border',
                              member.status === 'ACTIVE'
                                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                                : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                            )}
                          >
                            {member.status}
                          </span>
                        </td>
                        <td className="p-3.5 text-xs text-muted-foreground font-mono">
                          {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'N/A'}
                        </td>
                        <td className="p-3.5 text-right space-x-1">
                          {member.status === 'ACTIVE' ? (
                            <button
                              onClick={() => workspaceId && suspendMember(workspaceId, member.id)}
                              title="Suspend Member"
                              className="p-1.5 rounded text-muted-foreground hover:text-amber-500 hover:bg-muted transition-colors"
                            >
                              <UserX className="h-4 w-4" />
                            </button>
                          ) : (
                            <button
                              onClick={() => workspaceId && restoreMember(workspaceId, member.id)}
                              title="Restore Member"
                              className="p-1.5 rounded text-muted-foreground hover:text-emerald-500 hover:bg-muted transition-colors"
                            >
                              <UserCheck className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={() => {
                              if (confirm('Remove this member from the workspace?')) {
                                workspaceId && removeMember(workspaceId, member.id)
                              }
                            }}
                            title="Remove Member"
                            className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-muted transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'invitations' && (
        <div className="bg-card border border-border rounded-lg overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-foreground">
              <thead className="bg-muted/40 text-2xs uppercase text-muted-foreground font-mono tracking-wider border-b border-border">
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
                      <span className="text-xs font-mono">Loading invitations...</span>
                    </td>
                  </tr>
                ) : invitations.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="text-center py-12 text-muted-foreground">
                      <Mail className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                      <div className="text-sm font-medium text-foreground">No pending invitations</div>
                      <p className="text-xs text-muted-foreground mt-1">Use the invite button to onboard new team members.</p>
                    </td>
                  </tr>
                ) : (
                  invitations.map(inv => (
                    <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                      <td className="p-3.5 font-mono text-xs text-foreground font-medium">{inv.email}</td>
                      <td className="p-3.5 text-xs font-mono">
                        <span className={cn('px-2 py-0.5 rounded-full border text-2xs', getRoleBadgeClass(inv.role))}>
                          {inv.role}
                        </span>
                      </td>
                      <td className="p-3.5">
                        <span className="px-2 py-0.5 rounded-full text-2xs font-semibold font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          {inv.status}
                        </span>
                      </td>
                      <td className="p-3.5 text-xs text-muted-foreground font-mono">
                        {new Date(inv.expires_at).toLocaleString()}
                      </td>
                      <td className="p-3.5 text-right space-x-1">
                        {inv.status === 'PENDING' && (
                          <>
                            <button
                              onClick={async () => {
                                if (workspaceId) {
                                  await invitationService.resendInvitation(workspaceId, inv.id)
                                  loadInvitations()
                                }
                              }}
                              className="p-1.5 rounded text-muted-foreground hover:text-primary hover:bg-muted transition-colors"
                              title="Resend invitation link"
                            >
                              <RefreshCw className="h-4 w-4" />
                            </button>
                            <button
                              onClick={async () => {
                                if (workspaceId && confirm('Revoke this invitation?')) {
                                  await invitationService.revokeInvitation(workspaceId, inv.id)
                                  loadInvitations()
                                }
                              }}
                              className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-muted transition-colors"
                              title="Revoke invitation"
                            >
                              <Trash2 className="h-4 w-4" />
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

      {/* Invite Modal */}
      <AnimatePresence>
        {isInviteModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsInviteModalOpen(false)}
              className="fixed inset-0 bg-background/80 backdrop-blur-sm"
              aria-hidden="true"
            />
            <motion.div
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="relative bg-card border border-border rounded-xl p-6 w-full max-w-md shadow-xl space-y-5 z-10"
            >
              <div className="flex items-center justify-between border-b border-border/60 pb-3">
                <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                  <Mail className="h-4 w-4 text-primary" />
                  Invite Team Member
                </h2>
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {inviteSuccess ? (
                <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-3 text-emerald-500 text-sm">
                  <CheckCircle2 className="h-5 w-5 shrink-0" />
                  <span>{inviteSuccess}</span>
                </div>
              ) : (
                <form onSubmit={handleSendInvite} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="invite_email" className="text-xs font-semibold">
                      Email Address
                    </Label>
                    <Input
                      id="invite_email"
                      type="email"
                      required
                      value={inviteEmail}
                      onChange={e => setInviteEmail(e.target.value)}
                      placeholder="teammate@company.com"
                      className="h-9 text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="invite_role" className="text-xs font-semibold">
                      Workspace Role
                    </Label>
                    <select
                      id="invite_role"
                      value={inviteRole}
                      onChange={e => setInviteRole(e.target.value)}
                      className="w-full h-9 px-3 bg-background border border-input rounded-md text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                    >
                      <option value="ADMIN">ADMIN — Configure users, limits, and settings</option>
                      <option value="MEMBER">MEMBER — Query and upload knowledge documents</option>
                      <option value="VIEWER">VIEWER — Read-only access to existing documents</option>
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="invite_msg" className="text-xs font-semibold">
                      Custom Message (Optional)
                    </Label>
                    <textarea
                      id="invite_msg"
                      rows={3}
                      value={inviteMessage}
                      onChange={e => setInviteMessage(e.target.value)}
                      placeholder="Welcome to our project workspace..."
                      className="w-full px-3 py-2 bg-background border border-input rounded-md text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                  </div>

                  <div className="flex justify-end gap-2.5 pt-2 border-t border-border/60">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setIsInviteModalOpen(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={sendingInvite}
                      className="flex items-center gap-2"
                    >
                      {sendingInvite ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          <span>Sending...</span>
                        </>
                      ) : (
                        <>
                          <Send className="h-3.5 w-3.5" />
                          <span>Send Invitation</span>
                        </>
                      )}
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
