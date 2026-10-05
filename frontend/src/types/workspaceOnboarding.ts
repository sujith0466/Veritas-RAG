/**
 * Canonical Identity & Workspace Onboarding Types (WS-A1).
 *
 * Defines frontend contracts for:
 * - 5-way identifier separation
 * - Workspace preview and discovery (Mode 1, Mode 2, Mode 3)
 * - Workspace join requests
 * - Join code administration
 * - Active workspace switching
 */

export type JoiningMode = 'OPEN' | 'JOIN_CODE' | 'INVITE_ONLY';

/**
 * Safe public metadata for workspace preview prior to joining.
 * Excludes internal tenant UUID, member lists, and billing data.
 */
export interface WorkspacePreviewData {
  workspace_id: string; // Public Workspace ID (e.g. 'ACME-7X92')
  workspace_name: string;
  workspace_slug: string;
  joining_mode: JoiningMode;
  requires_join_code: boolean;
  open_join: boolean;
  require_approval: boolean;
  default_join_role: string;
}

export interface WorkspacePreviewResponse {
  success: boolean;
  message: string;
  data: WorkspacePreviewData;
}

/**
 * Payload for joining an existing workspace.
 * Uses public Workspace ID or Slug (never internal Tenant UUID).
 */
export interface JoinWorkspacePayload {
  workspace_id?: string | null;
  join_code?: string | null;
  invitation_token?: string | null;
}

export interface JoinWorkspaceResult {
  workspace_id: string; // Tenant UUID returned upon successful join
  workspace_name: string;
  role: string;
  status: string;
  member_id: string;
}

export interface JoinWorkspaceResponse {
  success: boolean;
  message: string;
  data: JoinWorkspaceResult;
}

/**
 * Administrative settings for Join Code configuration.
 * Plaintext code and code hash are NEVER exposed here.
 */
export interface JoinCodeSettings {
  enabled: boolean;
  default_role: 'MEMBER' | 'VIEWER';
  require_approval: boolean;
  expires_at?: string | null;
  generated_at?: string | null;
  generated_by?: string | null;
  has_code: boolean;
  max_uses?: number | null;
  current_uses?: number;
}

export interface JoinCodeSettingsPatchPayload {
  enabled?: boolean;
  default_role?: 'MEMBER' | 'VIEWER';
  require_approval?: boolean;
  max_uses?: number | null;
}

/**
 * Ephemeral result returned strictly once upon Join Code generation or regeneration.
 */
export interface JoinCodeGenerateResult {
  join_code: string; // Plaintext VR-XXXXXX displayed once
  expires_at?: string | null;
  default_role: string;
  warning: string;
}

export interface JoinCodeGenerateResponse {
  success: boolean;
  join_code: string;
  expires_at?: string | null;
  default_role: string;
  warning: string;
}

/**
 * Payload for switching the active workspace session context.
 */
export interface SwitchWorkspacePayload {
  workspace_id: string; // Internal target tenant UUID
}

export interface SwitchWorkspaceResult {
  workspace_id: string;
  workspace_public_id?: string | null;
  workspace_slug?: string | null;
  workspace_name: string;
  role: string;
  access_token: string;
  token_type: string;
}

export interface SwitchWorkspaceResponse {
  success: boolean;
  message: string;
  data: SwitchWorkspaceResult;
}

export interface CurrentWorkspaceData {
  workspace_id: string;
  public_id?: string | null;
  name: string;
  slug: string;
  role: string;
  status: string;
  joined_at?: string | null;
  updated_at?: string | null;
}

export interface CurrentWorkspaceResponse {
  success: boolean;
  data: CurrentWorkspaceData | null;
}

export interface UserWorkspaceMembership {
  workspace_id: string;
  public_id?: string | null;
  name: string;
  slug: string;
  role: string;
  status: string;
  is_active_context: boolean;
}

export interface UserWorkspacesListResponse {
  success: boolean;
  total: number;
  items: UserWorkspaceMembership[];
}

/**
 * Registration payload with optional onboarding context.
 */
export interface OnboardingRegistrationPayload {
  email: string;
  password: string;
  full_name?: string | null;
  workspace_id?: string | null;
  join_code?: string | null;
  invitation_token?: string | null;
  workspace_name?: string | null;
  company_name?: string | null;
}
