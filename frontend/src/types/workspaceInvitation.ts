/**
 * Types for Workspace Invitations (Epic 4: F4.1).
 */

export type InvitationStatus =
  | 'PENDING'
  | 'ACCEPTED'
  | 'REVOKED'
  | 'EXPIRED'
  | 'CANCELED';

export type WorkspaceRole = 'ADMIN' | 'MEMBER' | 'VIEWER';

export interface WorkspaceInvitation {
  id: string;
  workspace_id: string;
  email: string;
  role: WorkspaceRole | string;
  status: InvitationStatus;
  invited_by_user_id?: string | null;
  expires_at: string;
  accepted_at?: string | null;
  revoked_at?: string | null;
  resend_count: number;
  last_resent_at?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SendInvitationPayload {
  email: string;
  role?: WorkspaceRole | string;
  custom_message?: string;
}

export interface ResendInvitationPayload {
  custom_message?: string;
}

export interface VerifyInvitationData {
  invitation_id: string;
  workspace_id: string;
  workspace_name: string;
  email: string;
  role: string;
  inviter_email?: string | null;
  expires_at: string;
  status: InvitationStatus;
}

export interface WorkspaceInvitationListResult {
  items: WorkspaceInvitation[];
  total: number;
  page: number;
  page_size: number;
}

export interface AcceptInvitationPayload {
  token: string;
}

export interface AcceptInvitationResult {
  workspace_id: string;
  workspace_name: string;
  role: string;
  member_id: string;
}
