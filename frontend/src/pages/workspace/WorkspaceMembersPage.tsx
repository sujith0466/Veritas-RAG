import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMemberStore } from '@/stores/memberStore';
import { invitationService } from '@/services/invitationService';
import type { WorkspaceInvitation } from '@/types/workspaceInvitation';
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
} from 'lucide-react';

export const WorkspaceMembersPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
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
  } = useMemberStore();

  const [activeTab, setActiveTab] = useState<'members' | 'invitations'>('members');
  const [search, setSearch] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [selectedMembers, setSelectedMembers] = useState<string[]>([]);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState<boolean>(false);
  const [inviteEmail, setInviteEmail] = useState<string>('');
  const [inviteRole, setInviteRole] = useState<string>('MEMBER');
  const [inviteMessage, setInviteMessage] = useState<string>('');
  const [sendingInvite, setSendingInvite] = useState<boolean>(false);
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null);

  const [invitations, setInvitations] = useState<WorkspaceInvitation[]>([]);
  const [loadingInvitations, setLoadingInvitations] = useState<boolean>(false);

  useEffect(() => {
    if (workspaceId) {
      fetchMembers(workspaceId, { search, role: roleFilter || undefined });
      if (activeTab === 'invitations') {
        loadInvitations();
      }
    }
  }, [workspaceId, search, roleFilter, activeTab]);

  const loadInvitations = async () => {
    if (!workspaceId) return;
    try {
      setLoadingInvitations(true);
      const res = await invitationService.listInvitations(workspaceId);
      setInvitations(res.items);
    } catch (err) {
      console.error('Failed to load invitations', err);
    } finally {
      setLoadingInvitations(false);
    }
  };

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceId || !inviteEmail) return;
    try {
      setSendingInvite(true);
      clearError();
      await invitationService.sendInvitation(workspaceId, {
        email: inviteEmail,
        role: inviteRole,
        custom_message: inviteMessage || undefined,
      });
      setInviteSuccess(`Invitation sent to ${inviteEmail}`);
      setInviteEmail('');
      setInviteMessage('');
      setTimeout(() => {
        setIsInviteModalOpen(false);
        setInviteSuccess(null);
        if (activeTab === 'invitations') loadInvitations();
      }, 1500);
    } catch (err: any) {
      console.error('Failed to send invitation', err);
    } finally {
      setSendingInvite(false);
    }
  };

  const handleToggleSelectAll = () => {
    if (selectedMembers.length === members.length) {
      setSelectedMembers([]);
    } else {
      setSelectedMembers(members.map((m) => m.id));
    }
  };

  const handleToggleSelect = (id: string) => {
    setSelectedMembers((prev) =>
      prev.includes(id) ? prev.filter((mid) => mid !== id) : [...prev, id]
    );
  };

  const handleBulkAction = async (action: 'suspend' | 'restore' | 'remove') => {
    if (!workspaceId || selectedMembers.length === 0) return;
    if (confirm(`Are you sure you want to ${action} ${selectedMembers.length} selected member(s)?`)) {
      await bulkManage(workspaceId, { action, member_ids: selectedMembers });
      setSelectedMembers([]);
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 text-slate-100">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-5">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Users className="h-6 w-6 text-indigo-400" />
            Members & Permissions
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage workspace roles, access boundaries, and team members.
          </p>
        </div>
        <button
          onClick={() => setIsInviteModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium text-white transition-all shadow-lg shadow-indigo-600/20"
        >
          <UserPlus className="h-4 w-4" />
          Invite Team Member
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 gap-6">
        <button
          onClick={() => setActiveTab('members')}
          className={`pb-3 text-sm font-medium transition-all border-b-2 ${
            activeTab === 'members'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Active Members ({total})
        </button>
        <button
          onClick={() => setActiveTab('invitations')}
          className={`pb-3 text-sm font-medium transition-all border-b-2 ${
            activeTab === 'invitations'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          Pending Invitations
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-950/40 border border-red-800/50 flex items-center gap-3 text-red-200 text-sm">
          <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {activeTab === 'members' && (
        <>
          {/* Filters & Bulk Actions */}
          <div className="flex flex-col sm:flex-row justify-between gap-4 items-center bg-slate-900/60 p-4 rounded-xl border border-slate-800">
            <div className="flex flex-1 items-center gap-3 w-full sm:w-auto">
              <div className="relative flex-1">
                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search members by email or name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 bg-slate-800/80 border border-slate-750 rounded-lg text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
                />
              </div>
              <select
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
                className="bg-slate-800/80 border border-slate-750 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="">All Roles</option>
                <option value="OWNER">Owner</option>
                <option value="ADMIN">Admin</option>
                <option value="MEMBER">Member</option>
                <option value="VIEWER">Viewer</option>
              </select>
            </div>

            {selectedMembers.length > 0 && (
              <div className="flex items-center gap-2 text-xs font-medium">
                <span className="text-slate-400">{selectedMembers.length} selected:</span>
                <button
                  onClick={() => handleBulkAction('suspend')}
                  className="px-2.5 py-1.5 rounded-lg bg-amber-950/60 text-amber-300 border border-amber-800/60 hover:bg-amber-900/60"
                >
                  Suspend
                </button>
                <button
                  onClick={() => handleBulkAction('restore')}
                  className="px-2.5 py-1.5 rounded-lg bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 hover:bg-emerald-900/60"
                >
                  Restore
                </button>
                <button
                  onClick={() => handleBulkAction('remove')}
                  className="px-2.5 py-1.5 rounded-lg bg-red-950/60 text-red-300 border border-red-800/60 hover:bg-red-900/60"
                >
                  Remove
                </button>
              </div>
            )}
          </div>

          {/* Members Table */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/50 text-xs uppercase text-slate-400 tracking-wider border-b border-slate-800">
                <tr>
                  <th className="p-4 w-8">
                    <input
                      type="checkbox"
                      checked={selectedMembers.length > 0 && selectedMembers.length === members.length}
                      onChange={handleToggleSelectAll}
                      className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0"
                    />
                  </th>
                  <th className="p-4">User</th>
                  <th className="p-4">Role</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Joined At</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {isLoading ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      <Loader2 className="h-6 w-6 animate-spin mx-auto text-indigo-400 mb-2" />
                      Loading team members...
                    </td>
                  </tr>
                ) : members.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      No members found matching the criteria.
                    </td>
                  </tr>
                ) : (
                  members.map((member) => (
                    <tr key={member.id} className="hover:bg-slate-850/50 transition-colors">
                      <td className="p-4">
                        <input
                          type="checkbox"
                          checked={selectedMembers.includes(member.id)}
                          onChange={() => handleToggleSelect(member.id)}
                          className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0"
                        />
                      </td>
                      <td className="p-4 font-medium text-slate-200 flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-indigo-900/60 border border-indigo-700/50 flex items-center justify-center text-xs text-indigo-300 font-bold">
                          {member.user?.email?.[0]?.toUpperCase() || 'U'}
                        </div>
                        <div>
                          <div>{member.user?.email || member.user_id}</div>
                          {member.user?.username && (
                            <div className="text-xs text-slate-400">@{member.user.username}</div>
                          )}
                        </div>
                      </td>
                      <td className="p-4">
                        <select
                          value={member.role}
                          onChange={(e) =>
                            workspaceId && updateRole(workspaceId, member.id, e.target.value)
                          }
                          className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none"
                        >
                          <option value="OWNER">OWNER</option>
                          <option value="ADMIN">ADMIN</option>
                          <option value="MEMBER">MEMBER</option>
                          <option value="VIEWER">VIEWER</option>
                        </select>
                      </td>
                      <td className="p-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                            member.status === 'ACTIVE'
                              ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/50'
                              : 'bg-amber-950/60 text-amber-400 border border-amber-800/50'
                          }`}
                        >
                          {member.status}
                        </span>
                      </td>
                      <td className="p-4 text-xs text-slate-400">
                        {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="p-4 text-right space-x-2">
                        {member.status === 'ACTIVE' ? (
                          <button
                            onClick={() => workspaceId && suspendMember(workspaceId, member.id)}
                            title="Suspend Member"
                            className="p-1.5 text-slate-400 hover:text-amber-400 transition-colors"
                          >
                            <UserX className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => workspaceId && restoreMember(workspaceId, member.id)}
                            title="Restore Member"
                            className="p-1.5 text-slate-400 hover:text-emerald-400 transition-colors"
                          >
                            <UserCheck className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            if (confirm('Remove this member from the workspace?')) {
                              workspaceId && removeMember(workspaceId, member.id);
                            }
                          }}
                          title="Remove Member"
                          className="p-1.5 text-slate-400 hover:text-red-400 transition-colors"
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
        </>
      )}

      {activeTab === 'invitations' && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-800/50 text-xs uppercase text-slate-400 tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-4">Recipient Email</th>
                <th className="p-4">Role</th>
                <th className="p-4">Status</th>
                <th className="p-4">Expires At</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loadingInvitations ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto text-indigo-400 mb-2" />
                    Loading invitations...
                  </td>
                </tr>
              ) : invitations.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-8 text-slate-400">
                    No invitations found.
                  </td>
                </tr>
              ) : (
                invitations.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="p-4 font-mono text-xs text-slate-200">{inv.email}</td>
                    <td className="p-4 text-xs">{inv.role}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-950/60 text-indigo-300 border border-indigo-800/50">
                        {inv.status}
                      </span>
                    </td>
                    <td className="p-4 text-xs text-slate-400">
                      {new Date(inv.expires_at).toLocaleString()}
                    </td>
                    <td className="p-4 text-right space-x-2">
                      {inv.status === 'PENDING' && (
                        <>
                          <button
                            onClick={async () => {
                              if (workspaceId) {
                                await invitationService.resendInvitation(workspaceId, inv.id);
                                loadInvitations();
                              }
                            }}
                            className="p-1.5 text-slate-400 hover:text-indigo-400"
                            title="Resend magic link"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                          <button
                            onClick={async () => {
                              if (workspaceId && confirm('Revoke this invitation?')) {
                                await invitationService.revokeInvitation(workspaceId, inv.id);
                                loadInvitations();
                              }
                            }}
                            className="p-1.5 text-slate-400 hover:text-red-400"
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
      )}

      {/* Invite Modal */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-4">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Mail className="h-5 w-5 text-indigo-400" />
              Invite Team Member
            </h2>

            {inviteSuccess ? (
              <div className="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800/50 flex items-center gap-3 text-emerald-200 text-sm">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                <span>{inviteSuccess}</span>
              </div>
            ) : (
              <form onSubmit={handleSendInvite} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    placeholder="teammate@company.com"
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Workspace Role
                  </label>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="ADMIN">ADMIN (Manage users and resources)</option>
                    <option value="MEMBER">MEMBER (Create documents and queries)</option>
                    <option value="VIEWER">VIEWER (Read-only access)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">
                    Custom Message (Optional)
                  </label>
                  <textarea
                    rows={3}
                    value={inviteMessage}
                    onChange={(e) => setInviteMessage(e.target.value)}
                    placeholder="Welcome to our project workspace..."
                    className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsInviteModalOpen(false)}
                    className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={sendingInvite}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium text-white flex items-center gap-2 disabled:opacity-50"
                  >
                    {sendingInvite ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4" />
                        Send Invitation
                      </>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default WorkspaceMembersPage;
