import React from 'react';
import { Crown, Clock, Check, X, Shield, User, UserMinus } from 'lucide-react';
import { Button } from '@/components/common/Button';
import type { OwnershipTransferResponse } from '@/types/workspaceTransfer';

interface TransferPendingBannerProps {
  transfer: OwnershipTransferResponse;
  currentUserId: string;
  isOwner: boolean;
  onAccept: () => void;
  onReject: () => void;
  onCancel: () => void;
  onFormerOwnerChoice?: (choice: 'STAY' | 'LEAVE') => void;
  onRoleDecision?: (decision: 'ADMIN' | 'MEMBER' | 'REMOVE') => void;
}

export const TransferPendingBanner: React.FC<TransferPendingBannerProps> = ({
  transfer,
  currentUserId,
  isOwner,
  onAccept,
  onReject,
  onCancel,
  onFormerOwnerChoice,
  onRoleDecision,
}) => {
  // ---------------------------------------------------------------------------
  // State 5: Transfer Accepted, Former Owner Choice Pending
  // ---------------------------------------------------------------------------
  if (transfer.status === 'ACCEPTED' && transfer.former_owner_choice === 'PENDING') {
    const isFormerOwner = transfer.nominated_by?.id === currentUserId;

    if (isFormerOwner && onFormerOwnerChoice) {
      return (
        <div
          data-testid="former-owner-choice-banner"
          className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 mb-6 text-foreground flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-amber-500/20 text-amber-500 shrink-0 mt-0.5 sm:mt-0">
              <Crown className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                Ownership Transferred — Choose Workspace Disposition
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                Ownership was transferred to{' '}
                <span className="font-medium text-foreground font-mono">
                  {transfer.nominee?.full_name || transfer.nominee?.email}
                </span>
                . Please select whether you wish to remain in the workspace (STAY) pending role assignment or depart immediately (LEAVE).
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onFormerOwnerChoice('LEAVE')}
              className="text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
              data-testid="former-owner-leave-btn"
            >
              <X className="h-3.5 w-3.5 mr-1" />
              Leave Workspace
            </Button>
            <Button
              size="sm"
              onClick={() => onFormerOwnerChoice('STAY')}
              className="text-xs bg-amber-500 hover:bg-amber-600 text-white font-medium shadow-xs"
              data-testid="former-owner-stay-btn"
            >
              <Check className="h-3.5 w-3.5 mr-1" />
              Stay in Workspace
            </Button>
          </div>
        </div>
      );
    }
  }

  // ---------------------------------------------------------------------------
  // State 7: Former Owner Chose STAY, Role Decision Pending
  // ---------------------------------------------------------------------------
  if (
    transfer.status === 'ACCEPTED' &&
    transfer.former_owner_choice === 'STAY' &&
    transfer.decision_status === 'PENDING'
  ) {
    const isNewOwner = transfer.nominee?.id === currentUserId;
    const isFormerOwner = transfer.nominated_by?.id === currentUserId;

    if (isNewOwner && onRoleDecision) {
      return (
        <div
          data-testid="new-owner-role-decision-banner"
          className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4 mb-6 text-foreground flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400 shrink-0 mt-0.5 sm:mt-0">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
                Action Required: Assign Role to Former Owner
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                The former owner ({transfer.nominated_by?.full_name || transfer.nominated_by?.email}) chose to remain in the workspace.
                Assign an active role within 30 days, or they will be automatically granted the ADMIN role.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto justify-end flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => onRoleDecision('REMOVE')}
              className="text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
              data-testid="decision-remove-btn"
            >
              <UserMinus className="h-3.5 w-3.5 mr-1" />
              Remove
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onRoleDecision('MEMBER')}
              className="text-xs border-sky-500/40 text-sky-400 hover:bg-sky-500/10"
              data-testid="decision-member-btn"
            >
              <User className="h-3.5 w-3.5 mr-1" />
              Make Member
            </Button>
            <Button
              size="sm"
              onClick={() => onRoleDecision('ADMIN')}
              className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white font-medium"
              data-testid="decision-admin-btn"
            >
              <Shield className="h-3.5 w-3.5 mr-1" />
              Make Admin
            </Button>
          </div>
        </div>
      );
    }

    if (isFormerOwner) {
      return (
        <div
          data-testid="former-owner-waiting-banner"
          className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-4 mb-6 text-foreground flex items-center gap-3 animate-in fade-in"
        >
          <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400 shrink-0">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-foreground">
              Stay Request Registered
            </h4>
            <p className="text-xs text-muted-foreground mt-0.5">
              You chose to remain in the workspace. You will have full access once the workspace owner ({transfer.nominee.full_name || transfer.nominee.email}) assigns your role.
            </p>
          </div>
        </div>
      );
    }
  }

  // ---------------------------------------------------------------------------
  // State 2: Nomination Pending Acceptance / Rejection / Cancellation
  // ---------------------------------------------------------------------------
  if (transfer.status !== 'PENDING') {
    return null;
  }

  const isNominee = transfer.nominee.id === currentUserId;
  const expiresAt = new Date(transfer.expires_at);
  const formattedExpiry = expiresAt.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  const now = new Date();
  const diffMs = expiresAt.getTime() - now.getTime();
  const diffDays = Math.max(0, Math.ceil(diffMs / (1000 * 60 * 60 * 24)));

  if (isNominee) {
    return (
      <div
        data-testid="transfer-nominee-banner"
        className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 mb-6 text-foreground flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-500/20 text-amber-500 shrink-0 mt-0.5 sm:mt-0">
            <Crown className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
              Ownership Nomination Received
              <span className="inline-flex items-center gap-1 text-2xs font-mono font-normal text-amber-400 bg-amber-500/20 px-2 py-0.5 rounded-full">
                <Clock className="h-3 w-3" />
                {diffDays > 0 ? `${diffDays} day${diffDays === 1 ? '' : 's'} remaining` : 'Expiring soon'}
              </span>
            </h4>
            <p className="text-xs text-muted-foreground mt-0.5">
              You have been nominated to become Owner of this workspace by{' '}
              <span className="font-medium text-foreground font-mono">
                {transfer.nominated_by.full_name || transfer.nominated_by.email}
              </span>
              . Nomination expires on {formattedExpiry}.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <Button
            size="sm"
            variant="outline"
            onClick={onReject}
            className="text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
            data-testid="reject-transfer-btn"
          >
            <X className="h-3.5 w-3.5 mr-1" />
            Reject
          </Button>
          <Button
            size="sm"
            onClick={onAccept}
            className="text-xs bg-amber-500 hover:bg-amber-600 text-white font-medium shadow-xs"
            data-testid="accept-transfer-btn"
          >
            <Check className="h-3.5 w-3.5 mr-1" />
            Accept Ownership
          </Button>
        </div>
      </div>
    );
  }

  if (isOwner) {
    return (
      <div
        data-testid="transfer-owner-banner"
        className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4 mb-6 text-foreground flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-in fade-in"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400 shrink-0 mt-0.5 sm:mt-0">
            <Crown className="h-5 w-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
              Pending Ownership Transfer
              <span className="inline-flex items-center gap-1 text-2xs font-mono font-normal text-indigo-300 bg-indigo-500/20 px-2 py-0.5 rounded-full">
                <Clock className="h-3 w-3" />
                Expires {formattedExpiry}
              </span>
            </h4>
            <p className="text-xs text-muted-foreground mt-0.5">
              Ownership transfer to{' '}
              <span className="font-medium text-foreground font-mono">
                {transfer.nominee.full_name || transfer.nominee.email}
              </span>{' '}
              (nominated by {transfer.nominated_by.full_name || transfer.nominated_by.email}) is currently awaiting nominee response.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <Button
            size="sm"
            variant="outline"
            onClick={onCancel}
            className="text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
            data-testid="cancel-transfer-btn"
          >
            <X className="h-3.5 w-3.5 mr-1" />
            Cancel Transfer
          </Button>
        </div>
      </div>
    );
  }

  return null;
};
