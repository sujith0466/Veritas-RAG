import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { invitationService } from '@/services/invitationService';
import type { VerifyInvitationData } from '@/types/workspaceInvitation';
import { ShieldCheck, AlertTriangle, ArrowRight, CheckCircle2, Building2, UserCheck, Loader2 } from 'lucide-react';

export const AcceptInvitationPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [loading, setLoading] = useState<boolean>(true);
  const [accepting, setAccepting] = useState<boolean>(false);
  const [invitationData, setInvitationData] = useState<VerifyInvitationData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing invitation token. Please check your invitation link.');
      setLoading(false);
      return;
    }

    const verify = async () => {
      try {
        setLoading(true);
        const data = await invitationService.verifyInvitation(token);
        setInvitationData(data);
      } catch (err: any) {
        setError(
          err.response?.data?.detail ||
          err.message ||
          'Failed to verify workspace invitation. The link may have expired or been revoked.'
        );
      } finally {
        setLoading(false);
      }
    };

    verify();
  }, [token]);

  const handleAccept = async () => {
    if (!token) return;
    try {
      setAccepting(true);
      setError(null);
      await invitationService.acceptInvitation({ token });
      setSuccess(true);
      setTimeout(() => {
        navigate(`/workspaces`);
      }, 1500);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        err.message ||
        'Unable to accept invitation. Ensure your logged-in account matches the invitation email.'
      );
    } finally {
      setAccepting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 text-slate-100">
      <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-xl">
        <div className="flex justify-center mb-6">
          <div className="h-16 w-16 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <ShieldCheck className="h-8 w-8" />
          </div>
        </div>

        <h1 className="text-2xl font-bold text-center text-white tracking-tight">
          Workspace Invitation
        </h1>
        <p className="text-sm text-center text-slate-400 mt-2">
          Join your team securely on RAGuard Enterprise AI
        </p>

        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
            <span className="text-sm text-slate-400 mt-3">Verifying invitation token...</span>
          </div>
        )}

        {error && (
          <div className="mt-6 p-4 rounded-xl bg-red-950/40 border border-red-800/50 flex items-start space-x-3 text-red-200">
            <AlertTriangle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <div className="text-xs leading-relaxed">{error}</div>
          </div>
        )}

        {success && (
          <div className="mt-6 p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/50 flex items-center space-x-3 text-emerald-200">
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
            <div className="text-xs font-medium">
              Invitation accepted! Redirecting to workspace...
            </div>
          </div>
        )}

        {!loading && invitationData && !success && (
          <div className="mt-6 space-y-4">
            <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-750 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-4 w-4 text-indigo-400" />
                  Workspace
                </span>
                <span className="font-semibold text-slate-200">
                  {invitationData.workspace_name}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="flex items-center gap-1.5">
                  <UserCheck className="h-4 w-4 text-indigo-400" />
                  Assigned Role
                </span>
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">
                  {invitationData.role}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Invited Email</span>
                <span className="text-slate-300 font-mono text-xs">
                  {invitationData.email}
                </span>
              </div>
              {invitationData.inviter_email && (
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>Invited By</span>
                  <span className="text-slate-300 font-mono text-xs">
                    {invitationData.inviter_email}
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={handleAccept}
              disabled={accepting}
              className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-indigo-600/20"
            >
              {accepting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Joining Workspace...
                </>
              ) : (
                <>
                  Accept & Join Workspace
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default AcceptInvitationPage;
