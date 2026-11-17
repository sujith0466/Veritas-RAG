/**
 * Types for Workspace Ownership Transfer (Section 7 Batch 1 & Batch 2).
 */

export interface OwnershipTransferUserDTO {
  id: string;
  email: string;
  full_name?: string | null;
}

export type OwnershipTransferStatus =
  | 'PENDING'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'CANCELLED'
  | 'EXPIRED';

export type FormerOwnerChoice = 'PENDING' | 'STAY' | 'LEAVE';

export type DecisionStatus =
  | 'PENDING'
  | 'DECIDED_ADMIN'
  | 'DECIDED_MEMBER'
  | 'DECIDED_REMOVED'
  | 'FALLBACK_ADMIN'
  | 'TIMED_OUT';

export interface OwnershipTransferResponse {
  id: string;
  workspace_id: string;
  nominated_by: OwnershipTransferUserDTO;
  nominee: OwnershipTransferUserDTO;
  status: OwnershipTransferStatus;
  rejection_reason?: string | null;
  created_at: string;
  expires_at: string;
  responded_at?: string | null;
  cancelled_at?: string | null;
  expired_at?: string | null;
  is_expired: boolean;

  // Batch 2 Lifecycle fields
  former_owner_choice?: FormerOwnerChoice;
  former_owner_choice_at?: string | null;
  decision_status?: DecisionStatus;
  decision_deadline_at?: string | null;
  decided_at?: string | null;
  decided_by_user_id?: string | null;
  response_notes?: string | null;
  decision_notes?: string | null;
}

export interface OwnershipNominationCreate {
  nominee_user_id: string;
}

export interface OwnershipRejectionCreate {
  rejection_reason?: string;
}

export interface FormerOwnerChoiceCreate {
  choice: 'STAY' | 'LEAVE';
  notes?: string;
}

export interface RoleDecisionCreate {
  decision: 'ADMIN' | 'MEMBER' | 'REMOVE';
  notes?: string;
}
