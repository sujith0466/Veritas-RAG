/**
 * Types for Workspace Members (Epic 4: F4.3 & F4.4).
 */

export type MemberStatus = 'ACTIVE' | 'SUSPENDED' | 'LEFT';

export type WorkspaceRole = 'OWNER' | 'ADMIN' | 'MEMBER' | 'VIEWER' | 'ENGINEER' | 'ANALYST' | string;

export interface WorkspaceMemberUser {
  id: string;
  email: string;
  username?: string | null;
  is_active: boolean;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  role: WorkspaceRole;
  status: MemberStatus | string;
  invited_by_user_id?: string | null;
  joined_at?: string | null;
  last_active_at?: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  user?: WorkspaceMemberUser | null;
}

export interface WorkspaceMemberListResult {
  items: WorkspaceMember[];
  total: number;
  page: number;
  page_size: number;
  next_cursor?: string | null;
}

export interface UpdateRolePayload {
  role: string;
}

export interface BulkMemberActionPayload {
  action: 'suspend' | 'restore' | 'remove' | 'update_role';
  member_ids: string[];
  role?: string;
}

export interface BulkMemberActionResult {
  member_id: string;
  status: 'success' | 'error';
  message?: string;
}

export interface BulkMemberActionResponse {
  total: number;
  results: BulkMemberActionResult[];
}
