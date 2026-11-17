import React, { useState } from 'react';
import { Crown, AlertTriangle, X, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/common/Button';
import type { WorkspaceMember } from '@/types/workspaceMember';
import type { OwnershipTransferResponse } from '@/types/workspaceTransfer';

interface NominateOwnerModalProps {
  isOpen: boolean;
  member: WorkspaceMember | null;
  onClose: () => void;
  onConfirm: (memberId: string, userId: string) => Promise<void>;
  isLoading?: boolean;
}

export const NominateOwnerModal: React.FC<NominateOwnerModalProps> = ({
  isOpen,
  member,
  onClose,
  onConfirm,
  isLoading = false,
}) => {
  if (!isOpen || !member) return null;

  const displayName = member.user?.display_name || member.user?.username || member.user?.email || 'this member';
  const email = member.user?.email || '';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="nominate-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-xs animate-in fade-in"
    >
      <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-500">
            <Crown className="h-6 w-6" />
          </div>
          <div>
            <h3 id="nominate-modal-title" className="text-base font-semibold text-foreground">
              Nominate New Workspace Owner
            </h3>
            <p className="text-xs text-muted-foreground">7-Day Transfer Invitation</p>
          </div>
        </div>

        <div className="text-xs text-muted-foreground space-y-2 border-y border-border/60 py-3">
          <p>
            You are nominating <strong className="text-foreground">{displayName}</strong> ({email}) to become the sole Owner of this workspace.
          </p>
          <ul className="list-disc list-inside space-y-1 text-2xs text-muted-foreground/90">
            <li>The nominee will have <strong className="text-foreground">7 days</strong> to accept or reject this nomination.</li>
            <li>Upon acceptance, they will receive full Owner privileges.</li>
            <li>You will be demoted from Owner to <strong className="text-foreground">MEMBER</strong> upon acceptance.</li>
            <li>You can cancel this nomination at any time before they accept.</li>
          </ul>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            size="sm"
            className="bg-amber-500 hover:bg-amber-600 text-white font-medium"
            onClick={() => onConfirm(member.id, member.user_id)}
            disabled={isLoading}
            data-testid="confirm-nomination-btn"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Crown className="h-4 w-4 mr-1" />}
            Send Ownership Nomination
          </Button>
        </div>
      </div>
    </div>
  );
};

interface AcceptTransferModalProps {
  isOpen: boolean;
  transfer: OwnershipTransferResponse | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isLoading?: boolean;
}

export const AcceptTransferModal: React.FC<AcceptTransferModalProps> = ({
  isOpen,
  transfer,
  onClose,
  onConfirm,
  isLoading = false,
}) => {
  if (!isOpen || !transfer) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="accept-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-xs animate-in fade-in"
    >
      <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-500">
            <Crown className="h-6 w-6" />
          </div>
          <div>
            <h3 id="accept-modal-title" className="text-base font-semibold text-foreground">
              Accept Workspace Ownership
            </h3>
            <p className="text-xs text-muted-foreground">Assume supreme control of this workspace</p>
          </div>
        </div>

        <div className="text-xs text-muted-foreground space-y-2 border-y border-border/60 py-3">
          <p>
            By accepting, you will become the <strong className="text-foreground">sole Workspace Owner</strong>.
          </p>
          <ul className="list-disc list-inside space-y-1 text-2xs text-muted-foreground/90">
            <li>You will control billing, quotas, invitations, and workspace deletion.</li>
            <li>The previous owner will be demoted to Member.</li>
            <li>This action takes effect immediately and cannot be undone except by a subsequent transfer.</li>
          </ul>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            size="sm"
            className="bg-amber-500 hover:bg-amber-600 text-white font-medium"
            onClick={onConfirm}
            disabled={isLoading}
            data-testid="confirm-accept-transfer-btn"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Check className="h-4 w-4 mr-1" />}
            Confirm & Become Owner
          </Button>
        </div>
      </div>
    </div>
  );
};

interface RejectTransferModalProps {
  isOpen: boolean;
  transfer: OwnershipTransferResponse | null;
  onClose: () => void;
  onConfirm: (reason?: string) => Promise<void>;
  isLoading?: boolean;
}

export const RejectTransferModal: React.FC<RejectTransferModalProps> = ({
  isOpen,
  transfer,
  onClose,
  onConfirm,
  isLoading = false,
}) => {
  const [reason, setReason] = useState('');

  if (!isOpen || !transfer) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="reject-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-xs animate-in fade-in"
    >
      <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-destructive/10 text-destructive">
            <X className="h-6 w-6" />
          </div>
          <div>
            <h3 id="reject-modal-title" className="text-base font-semibold text-foreground">
              Decline Ownership Nomination
            </h3>
            <p className="text-xs text-muted-foreground">Keep your current workspace role</p>
          </div>
        </div>

        <div className="text-xs text-muted-foreground space-y-3 border-y border-border/60 py-3">
          <p>
            You are declining ownership of this workspace. The nominator will remain Owner and will be notified of your decision.
          </p>
          <div>
            <label htmlFor="rejection-reason" className="block text-2xs font-medium text-foreground mb-1">
              Feedback for Nominator (Optional, max 500 characters):
            </label>
            <textarea
              id="rejection-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value.slice(0, 500))}
              placeholder="e.g. I do not have the capacity to take on ownership responsibilities at this time."
              rows={3}
              className="w-full p-2 text-xs border border-border rounded-md bg-background focus:outline-none focus:ring-1 focus:ring-primary"
            />
            <div className="text-right text-3xs text-muted-foreground mt-0.5">
              {reason.length}/500
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Back
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => onConfirm(reason.trim() || undefined)}
            disabled={isLoading}
            data-testid="confirm-reject-transfer-btn"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <X className="h-4 w-4 mr-1" />}
            Decline Ownership
          </Button>
        </div>
      </div>
    </div>
  );
};

interface CancelTransferModalProps {
  isOpen: boolean;
  transfer: OwnershipTransferResponse | null;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  isLoading?: boolean;
}

export const CancelTransferModal: React.FC<CancelTransferModalProps> = ({
  isOpen,
  transfer,
  onClose,
  onConfirm,
  isLoading = false,
}) => {
  if (!isOpen || !transfer) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-xs animate-in fade-in"
    >
      <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg p-6 space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-500">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div>
            <h3 id="cancel-modal-title" className="text-base font-semibold text-foreground">
              Cancel Pending Transfer
            </h3>
            <p className="text-xs text-muted-foreground">Withdraw ownership nomination</p>
          </div>
        </div>

        <div className="text-xs text-muted-foreground space-y-2 border-y border-border/60 py-3">
          <p>
            Are you sure you want to cancel the pending ownership nomination for{' '}
            <strong className="text-foreground">
              {transfer.nominee.full_name || transfer.nominee.email}
            </strong>?
          </p>
          <p className="text-2xs text-muted-foreground/90">
            The nominee will be notified in-app that the nomination was cancelled. You will remain the Owner.
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isLoading}>
            Keep Nomination
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={onConfirm}
            disabled={isLoading}
            data-testid="confirm-cancel-transfer-btn"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <X className="h-4 w-4 mr-1" />}
            Confirm Cancellation
          </Button>
        </div>
      </div>
    </div>
  );
};
