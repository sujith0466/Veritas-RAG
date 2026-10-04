import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useWorkspaceStore } from '@/stores/workspaceStore';
import { workspaceService } from '@/services/workspaceService';
import { invitationService } from '@/services/invitationService';
import type { WorkspacePreviewData } from '@/types';
import type { VerifyInvitationData } from '@/types/workspaceInvitation';
import {
  KeyRound,
  Mail,
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Building2,
  Search,
  Clock,
  ExternalLink,
} from 'lucide-react';

const TENANT_UUID_REGEX = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
const CROCKFORD_JOIN_CODE_REGEX = /^VR-[23456789ABCDEFGHJKMNPQRSTVWXYZ]{6}$/;

export const JoinWorkspacePage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { joinWorkspace, switchWorkspace, isLoading, error, clearError } = useWorkspaceStore();

  const [activeTab, setActiveTab] = useState<'code' | 'invitation'>('code');

  // Mode 1 & 2 state
  const [workspaceIdentifier, setWorkspaceIdentifier] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [preview, setPreview] = useState<WorkspacePreviewData | null>(null);
  const [isLookingUp, setIsLookingUp] = useState(false);

  // Mode 3 state
  const [invitationToken, setInvitationToken] = useState('');
  const [invitationPreview, setInvitationPreview] = useState<VerifyInvitationData | null>(null);
  const [isVerifyingInvite, setIsVerifyingInvite] = useState(false);

  // Shared UX states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [conflictWorkspaceId, setConflictWorkspaceId] = useState<string | null>(null);
  const [isPendingApproval, setIsPendingApproval] = useState(false);
  const [joinSuccess, setJoinSuccess] = useState<string | null>(null);

  // Pre-populate transient search params
  useEffect(() => {
    const wsId = searchParams.get('workspace_id') || searchParams.get('workspace');
    const code = searchParams.get('join_code') || searchParams.get('code');
    const token = searchParams.get('invitation_token') || searchParams.get('token');

    if (token) {
      setInvitationToken(token.trim());
      setActiveTab('invitation');
    }
    if (wsId) {
      setWorkspaceIdentifier(wsId.trim());
    }
    if (code) {
      let formattedCode = code.trim().toUpperCase();
      if (formattedCode.length === 6 && !formattedCode.startsWith('VR-')) {
        formattedCode = `VR-${formattedCode}`;
      }
      setJoinCode(formattedCode);
    }

    // Sanitize credentials from URL bar to prevent leakage in browser history/screen capture
    if (token || code) {
      const cleanParams = new URLSearchParams(window.location.search);
      cleanParams.delete('token');
      cleanParams.delete('invitation_token');
      cleanParams.delete('code');
      cleanParams.delete('join_code');
      const cleanQuery = cleanParams.toString() ? `?${cleanParams.toString()}` : '';
      window.history.replaceState(null, '', `${window.location.pathname}${cleanQuery}`);
    }
  }, [searchParams]);

  // Lookup / Preview Workspace (Mode 1 & 2)
  const handleLookup = async (identifierToLookup?: string) => {
    const id = (identifierToLookup || workspaceIdentifier).trim();
    if (!id) return;

    if (TENANT_UUID_REGEX.test(id)) {
      setClientError('Internal Tenant UUID cannot be used. Please provide the public Workspace ID or slug.');
      return;
    }

    setClientError(null);
    clearError();
    setIsLookingUp(true);
    setConflictWorkspaceId(null);

    try {
      const res = await workspaceService.lookupWorkspace(id);
      const previewData = (res as any)?.data || res;
      if (previewData && previewData.workspace_name) {
        setPreview(previewData);
      }
    } catch (err: any) {
      setPreview(null);
      setClientError(err?.response?.data?.detail || 'Workspace not found. Check the identifier and try again.');
    } finally {
      setIsLookingUp(false);
    }
  };

  // Verify Invitation Token (Mode 3)
  const handleVerifyInvite = async (tokenToVerify?: string) => {
    const rawToken = (tokenToVerify || invitationToken).trim();
    if (!rawToken) return;

    setClientError(null);
    clearError();
    setIsVerifyingInvite(true);
    setConflictWorkspaceId(null);

    try {
      const res = await invitationService.verifyInvitation(rawToken);
      const inviteData = (res as any)?.data || res;
      setInvitationPreview(inviteData);
    } catch (err: any) {
      setInvitationPreview(null);
      setClientError(
        err?.response?.data?.detail || 'Invalid or expired invitation token. Please check your invitation link.'
      );
    } finally {
      setIsVerifyingInvite(false);
    }
  };

  // Submit Join via Workspace ID + Join Code (Mode 1 & 2)
  const handleJoinByCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setClientError(null);
    clearError();
    setConflictWorkspaceId(null);

    const cleanId = workspaceIdentifier.trim();
    if (!cleanId) {
      setClientError('Workspace ID or slug is required.');
      return;
    }

    if (TENANT_UUID_REGEX.test(cleanId)) {
      setClientError('Internal Tenant UUID cannot be used as a join credential.');
      return;
    }

    let cleanCode = joinCode.trim().toUpperCase() || undefined;
    if (cleanCode) {
      if (!cleanCode.startsWith('VR-') && cleanCode.length === 6) {
        cleanCode = `VR-${cleanCode}`;
      }
      if (!CROCKFORD_JOIN_CODE_REGEX.test(cleanCode)) {
        setClientError('Invalid Join Code format. Expected "VR-XXXXXX" with 6 Crockford Base32 characters (excluding 0, O, 1, I, L).');
        return;
      }
    }

    // Double-submit protection
    if (isSubmitting || isLoading) return;

    try {
      setIsSubmitting(true);
      const result = await joinWorkspace({
        workspace_id: cleanId,
        join_code: cleanCode,
      });

      if (result.status === 'PENDING_APPROVAL') {
        setIsPendingApproval(true);
      } else {
        setJoinSuccess(`Successfully joined ${result.workspace_name}! Redirecting...`);
        setTimeout(() => {
          navigate('/dashboard', { replace: true });
        }, 1200);
      }
    } catch (err: any) {
      const status = err?.response?.status || err?.status || err?.statusCode;
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        '';

      if (status === 409 || detail.toLowerCase().includes('already a member')) {
        setConflictWorkspaceId(cleanId);
        setClientError('You are already an active member of this workspace.');
      } else {
        setClientError(detail || 'Failed to join workspace.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Submit Join via Invitation Token (Mode 3)
  const handleJoinByInvitation = async (e: React.FormEvent) => {
    e.preventDefault();
    setClientError(null);
    clearError();
    setConflictWorkspaceId(null);

    const rawToken = invitationToken.trim();
    if (!rawToken) {
      setClientError('Invitation token is required.');
      return;
    }

    // Double-submit protection
    if (isSubmitting || isLoading) return;

    try {
      setIsSubmitting(true);
      const res = await invitationService.acceptInvitation({ token: rawToken });
      // Authoritatively switch active workspace context to the newly accepted workspace
      await switchWorkspace(res.workspace_id);
      setJoinSuccess(`Invitation accepted for ${res.workspace_name}! Redirecting...`);
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 1200);
    } catch (err: any) {
      const status = err?.response?.status || err?.status || err?.statusCode;
      const detail =
        err?.response?.data?.detail ||
        err?.response?.data?.error?.message ||
        err?.message ||
        '';

      if (status === 409 || detail.toLowerCase().includes('already a member')) {
        setConflictWorkspaceId(invitationPreview?.workspace_id || 'workspace');
        setClientError('You are already an active member of this workspace.');
      } else {
        setClientError(
          detail || 'Unable to accept invitation. Ensure your logged-in account matches the invited email.'
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Switch to conflict workspace if user already has membership
  const handleSwitchToExisting = async () => {
    if (!conflictWorkspaceId) return;
    try {
      setIsSubmitting(true);
      await switchWorkspace(conflictWorkspaceId);
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      setClientError(err?.response?.data?.detail || 'Failed to switch to workspace.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const activeError = clientError || error;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center py-12 px-4 sm:px-6 lg:px-8 text-slate-100">
      <div className="sm:mx-auto sm:w-full sm:max-w-lg">
        <button
          type="button"
          onClick={() => navigate('/onboarding')}
          className="inline-flex items-center text-xs font-medium text-slate-400 hover:text-slate-200 transition-colors mb-6 group"
        >
          <ArrowLeft className="h-4 w-4 mr-1.5 transition-transform group-hover:-translate-x-1" />
          Back to Onboarding
        </button>

        <div className="flex justify-center mb-4">
          <div className="h-14 w-14 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            <KeyRound className="h-7 w-7" />
          </div>
        </div>

        <h1 className="text-center text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
          Join an Existing Workspace
        </h1>
        <p className="mt-2 text-center text-xs sm:text-sm text-slate-400">
          Enter with a Workspace ID, a 6-character Join Code, or an Invitation Token.
        </p>

        {/* Mode Selector Tabs */}
        <div className="mt-6 flex rounded-xl bg-slate-900/90 p-1 border border-slate-800">
          <button
            type="button"
            onClick={() => {
              setActiveTab('code');
              setClientError(null);
              clearError();
            }}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center space-x-2 ${
              activeTab === 'code'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <KeyRound className="h-3.5 w-3.5" />
            <span>Workspace ID / Code</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('invitation');
              setClientError(null);
              clearError();
            }}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all flex items-center justify-center space-x-2 ${
              activeTab === 'invitation'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Mail className="h-3.5 w-3.5" />
            <span>Invitation Token</span>
          </button>
        </div>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-lg">
        <div className="bg-slate-900 border border-slate-800 py-8 px-6 shadow-2xl rounded-2xl sm:px-10 backdrop-blur-xl">
          {/* Success Banner */}
          {joinSuccess && (
            <div className="mb-6 p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/50 flex items-center space-x-3 text-emerald-200">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
              <div className="text-xs font-medium">{joinSuccess}</div>
            </div>
          )}

          {/* Pending Approval Notice */}
          {isPendingApproval && (
            <div className="mb-6 p-5 rounded-xl bg-amber-950/40 border border-amber-800/50 space-y-3 text-amber-200">
              <div className="flex items-center space-x-2.5 font-semibold text-sm text-amber-300">
                <Clock className="h-5 w-5" />
                <span>Approval Required</span>
              </div>
              <p className="text-xs leading-relaxed text-amber-200/90">
                Your request to join this workspace has been recorded and is currently pending administrator approval.
                You will receive confirmation once an administrator reviews your request.
              </p>
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => navigate('/onboarding')}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-medium transition-colors"
                >
                  Return to Onboarding
                </button>
              </div>
            </div>
          )}

          {/* Error Banner */}
          {activeError && !isPendingApproval && (
            <div className="mb-6 p-4 rounded-xl bg-red-950/40 border border-red-800/50 space-y-2 text-red-200">
              <div className="flex items-start space-x-3">
                <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
                <div className="text-xs leading-relaxed">{activeError}</div>
              </div>
              {conflictWorkspaceId && (
                <div className="pl-8 pt-1">
                  <button
                    type="button"
                    onClick={handleSwitchToExisting}
                    disabled={isSubmitting}
                    className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    <span>Switch to this Workspace</span>
                    <ExternalLink className="h-3 w-3 ml-1" />
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 1: Mode 1 & 2 (Workspace ID + Join Code) */}
          {activeTab === 'code' && !isPendingApproval && (
            <form className="space-y-6" onSubmit={handleJoinByCode}>
              <div>
                <label
                  htmlFor="workspace-identifier"
                  className="block text-xs font-medium uppercase tracking-wider text-slate-300"
                >
                  Workspace ID or Slug <span className="text-indigo-400">*</span>
                </label>
                <div className="mt-2 flex space-x-2">
                  <input
                    id="workspace-identifier"
                    name="workspace-identifier"
                    type="text"
                    required
                    value={workspaceIdentifier}
                    onChange={(e) => {
                      setWorkspaceIdentifier(e.target.value);
                      setPreview(null);
                      setClientError(null);
                    }}
                    onBlur={() => {
                      if (workspaceIdentifier.trim() && !preview && !isLookingUp) {
                        handleLookup();
                      }
                    }}
                    className="block flex-1 px-3.5 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm transition-all"
                    placeholder="e.g. ACME-7X92 or acme-ai"
                    disabled={isLoading || isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => handleLookup()}
                    disabled={isLookingUp || !workspaceIdentifier.trim() || isLoading}
                    className="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs font-medium text-slate-200 transition-colors disabled:opacity-50 flex items-center space-x-1.5"
                  >
                    {isLookingUp ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    <span>Lookup</span>
                  </button>
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  Enter the public identifier or URL slug provided by the workspace admin.
                </p>
              </div>

              {/* Workspace Preview Badge */}
              {preview && (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 rounded-lg bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{preview.workspace_name}</div>
                      <div className="text-xs text-slate-400">
                        {preview.workspace_id} &bull; {preview.default_join_role}
                      </div>
                    </div>
                  </div>
                  <div>
                    {preview.requires_join_code ? (
                      <span className="text-[11px] font-medium text-indigo-300 bg-indigo-950/60 border border-indigo-800/60 px-2 py-0.5 rounded-full">
                        Requires Code
                      </span>
                    ) : (
                      <span className="text-[11px] font-medium text-emerald-300 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-full">
                        Open Join
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Join Code Input (Mode 2) */}
              <div>
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="join-code"
                    className="block text-xs font-medium uppercase tracking-wider text-slate-300"
                  >
                    Join Code {preview?.requires_join_code && <span className="text-indigo-400">*</span>}
                  </label>
                  {!preview?.requires_join_code && (
                    <span className="text-[11px] text-slate-500">Optional for open workspaces</span>
                  )}
                </div>
                <div className="mt-2">
                  <input
                    id="join-code"
                    name="join-code"
                    type="text"
                    maxLength={9}
                    value={joinCode}
                    onChange={(e) => {
                      let val = e.target.value.toUpperCase();
                      setJoinCode(val);
                      setClientError(null);
                    }}
                    onBlur={() => {
                      let val = joinCode.trim().toUpperCase();
                      if (val.length === 6 && !val.startsWith('VR-')) {
                        setJoinCode(`VR-${val}`);
                      }
                    }}
                    className="block w-full px-3.5 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm font-mono tracking-wider transition-all uppercase"
                    placeholder="VR-XXXXXX"
                    disabled={isLoading || isSubmitting}
                  />
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  Format: <code className="text-slate-400">VR-XXXXXX</code> (6 Crockford Base32 characters, excluding 0, O, 1, I, L).
                </p>
              </div>

              <div>
                <button
                  type="submit"
                  disabled={isLoading || isSubmitting || !workspaceIdentifier.trim()}
                  className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-xl shadow-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {isLoading || isSubmitting ? (
                    <span className="flex items-center space-x-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Verifying & Joining...</span>
                    </span>
                  ) : (
                    <span className="flex items-center space-x-2">
                      <KeyRound className="h-4 w-4" />
                      <span>Join Workspace</span>
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* TAB 2: Mode 3 (Invitation Token) */}
          {activeTab === 'invitation' && !isPendingApproval && (
            <form className="space-y-6" onSubmit={handleJoinByInvitation}>
              <div>
                <label
                  htmlFor="invitation-token"
                  className="block text-xs font-medium uppercase tracking-wider text-slate-300"
                >
                  Invitation Token <span className="text-indigo-400">*</span>
                </label>
                <div className="mt-2 flex space-x-2">
                  <input
                    id="invitation-token"
                    name="invitation-token"
                    type="text"
                    required
                    value={invitationToken}
                    onChange={(e) => {
                      setInvitationToken(e.target.value);
                      setInvitationPreview(null);
                      setClientError(null);
                    }}
                    onBlur={() => {
                      if (invitationToken.trim() && !invitationPreview && !isVerifyingInvite) {
                        handleVerifyInvite();
                      }
                    }}
                    className="block flex-1 px-3.5 py-2.5 bg-slate-950 border border-slate-700/80 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm font-mono text-xs transition-all"
                    placeholder="Paste your invitation token (sec_inv_...)"
                    disabled={isLoading || isSubmitting}
                  />
                  <button
                    type="button"
                    onClick={() => handleVerifyInvite()}
                    disabled={isVerifyingInvite || !invitationToken.trim() || isLoading}
                    className="px-3.5 py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs font-medium text-slate-200 transition-colors disabled:opacity-50 flex items-center space-x-1.5"
                  >
                    {isVerifyingInvite ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                    <span>Verify</span>
                  </button>
                </div>
                <p className="mt-1.5 text-xs text-slate-500">
                  Provided in your email invitation link or directly by an administrator.
                </p>
              </div>

              {/* Invitation Preview Card */}
              {invitationPreview && (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                  <div className="flex items-center space-x-3">
                    <div className="h-10 w-10 rounded-lg bg-emerald-600/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-white">{invitationPreview.workspace_name}</div>
                      <div className="text-xs text-slate-400">
                        Assigned Role: <span className="text-slate-200 font-medium">{invitationPreview.role}</span>
                      </div>
                    </div>
                  </div>
                  {invitationPreview.email && (
                    <div className="text-xs text-slate-400 pt-1 border-t border-slate-800/80">
                      Invited Email: <span className="text-slate-300">{invitationPreview.email}</span>
                    </div>
                  )}
                </div>
              )}

              <div>
                <button
                  type="submit"
                  disabled={isLoading || isSubmitting || !invitationToken.trim()}
                  className="w-full flex justify-center items-center py-2.5 px-4 border border-transparent rounded-xl shadow-lg text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-900 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  {isLoading || isSubmitting ? (
                    <span className="flex items-center space-x-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Accepting Invitation...</span>
                    </span>
                  ) : (
                    <span className="flex items-center space-x-2">
                      <Mail className="h-4 w-4" />
                      <span>Accept & Join Workspace</span>
                    </span>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
