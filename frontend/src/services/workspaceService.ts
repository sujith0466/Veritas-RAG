import { get, post, patch } from '@/api/wrapper';
import type {
  WorkspacePreviewResponse,
  JoinCodeSettings,
  JoinCodeSettingsPatchPayload,
  JoinCodeGenerateResponse,
  SwitchWorkspaceResponse,
  CurrentWorkspaceResponse,
  UserWorkspacesListResponse,
  JoinWorkspacePayload,
  JoinWorkspaceResponse,
} from '@/types';

export interface Workspace {
  id: string;
  public_id?: string;
  name: string;
  slug: string;
  status: string;
  provisioning_status: string;
  updated_at: string;
  suspended_at?: string | null;
}

export type SuspensionReasonCode =
  | 'BILLING'
  | 'SECURITY'
  | 'ABUSE'
  | 'LEGAL'
  | 'COMPLIANCE'
  | 'MANUAL'
  | 'OTHER';

export interface WorkspaceResponse {
  success: boolean;
  data: Workspace;
}

class WorkspaceService {
  /**
   * Create a new workspace
   */
  async createWorkspace(name: string, description?: string): Promise<WorkspaceResponse> {
    const response = await post<WorkspaceResponse>('/api/v1/workspaces', {
      name,
      description
    });
    return response;
  }

  /**
   * Get workspace details by ID
   */
  async getWorkspace(id: string): Promise<WorkspaceResponse> {
    const response = await get<WorkspaceResponse>(`/api/v1/workspaces/${id}`);
    return response;
  }

  /**
   * Resolve public workspace preview by Workspace ID or slug
   */
  async lookupWorkspace(identifier: string): Promise<WorkspacePreviewResponse> {
    const response = await get<WorkspacePreviewResponse>(
      `/api/v1/workspaces/lookup?identifier=${encodeURIComponent(identifier)}`
    );
    return response;
  }

  /**
   * Join an existing workspace (WS-A8)
   */
  async joinWorkspace(payload: JoinWorkspacePayload): Promise<JoinWorkspaceResponse> {
    const response = await post<JoinWorkspaceResponse>(
      '/api/v1/workspaces/join',
      payload
    );
    return response;
  }

  /**
   * Update an existing workspace
   */
  async updateWorkspace(
    id: string,
    expectedUpdatedAt: string,
    name?: string,
    description?: string
  ): Promise<WorkspaceResponse> {
    const response = await patch<WorkspaceResponse>(`/api/v1/workspaces/${id}`, {
      expected_updated_at: expectedUpdatedAt,
      name,
      description
    });
    return response;
  }

  /**
   * Archive a workspace
   */
  async archiveWorkspace(
    id: string,
    expectedUpdatedAt: string,
    confirmationName: string,
    reason?: string
  ): Promise<WorkspaceResponse> {
    const response = await post<WorkspaceResponse>(`/api/v1/workspaces/${id}/archive`, {
      expected_updated_at: expectedUpdatedAt,
      confirmation_name: confirmationName,
      reason
    });
    return response;
  }

  /**
   * Restore an archived workspace
   */
  async restoreWorkspace(
    id: string,
    expectedUpdatedAt: string
  ): Promise<WorkspaceResponse> {
    const response = await post<WorkspaceResponse>(`/api/v1/workspaces/${id}/restore`, {
      expected_updated_at: expectedUpdatedAt
    });
    return response;
  }

  /**
   * Suspend a workspace (Platform Admin only)
   */
  async suspendWorkspace(
    id: string,
    expectedUpdatedAt: string,
    confirmationName: string,
    reasonCode: SuspensionReasonCode,
    reasonText?: string
  ): Promise<WorkspaceResponse> {
    const response = await post<WorkspaceResponse>(`/api/v1/workspaces/${id}/suspend`, {
      expected_updated_at: expectedUpdatedAt,
      confirmation_name: confirmationName,
      reason_code: reasonCode,
      reason_text: reasonText
    });
    return response;
  }

  /**
   * Unsuspend a workspace (Platform Admin only)
   */
  async unsuspendWorkspace(
    id: string,
    expectedUpdatedAt: string,
    reasonText?: string
  ): Promise<WorkspaceResponse> {
    const response = await post<WorkspaceResponse>(`/api/v1/workspaces/${id}/unsuspend`, {
      expected_updated_at: expectedUpdatedAt,
      reason_text: reasonText
    });
    return response;
  }

  /**
   * Get join code settings for a workspace (Admin/Owner only)
   */
  async getJoinCodeSettings(workspaceId: string): Promise<JoinCodeSettings> {
    const response = await get<JoinCodeSettings>(`/api/v1/workspaces/${workspaceId}/join-code`);
    return response;
  }

  /**
   * Update join code settings for a workspace (Admin/Owner only)
   */
  async patchJoinCodeSettings(
    workspaceId: string,
    payload: JoinCodeSettingsPatchPayload
  ): Promise<JoinCodeSettings> {
    const response = await patch<JoinCodeSettings>(
      `/api/v1/workspaces/${workspaceId}/join-code/settings`,
      payload
    );
    return response;
  }

  /**
   * Generate a new join code (Admin/Owner only)
   */
  async generateJoinCode(
    workspaceId: string,
    params?: {
      expires_in_days?: number;
      default_role?: 'MEMBER' | 'VIEWER';
      require_approval?: boolean;
      max_uses?: number | null;
    }
  ): Promise<JoinCodeGenerateResponse> {
    const q = new URLSearchParams();
    if (params?.expires_in_days !== undefined) q.set('expires_in_days', String(params.expires_in_days));
    if (params?.default_role) q.set('default_role', params.default_role);
    if (params?.require_approval !== undefined) q.set('require_approval', String(params.require_approval));
    if (params?.max_uses !== undefined && params?.max_uses !== null) q.set('max_uses', String(params.max_uses));
    const qs = q.toString() ? `?${q.toString()}` : '';
    const response = await post<JoinCodeGenerateResponse>(
      `/api/v1/workspaces/${workspaceId}/join-code/generate${qs}`
    );
    return response;
  }

  /**
   * Regenerate join code (Admin/Owner only)
   */
  async regenerateJoinCode(
    workspaceId: string,
    params?: {
      expires_in_days?: number;
      max_uses?: number | null;
    }
  ): Promise<JoinCodeGenerateResponse> {
    const q = new URLSearchParams();
    if (params?.expires_in_days !== undefined) q.set('expires_in_days', String(params.expires_in_days));
    if (params?.max_uses !== undefined && params?.max_uses !== null) q.set('max_uses', String(params.max_uses));
    const qs = q.toString() ? `?${q.toString()}` : '';
    const response = await post<JoinCodeGenerateResponse>(
      `/api/v1/workspaces/${workspaceId}/join-code/regenerate${qs}`
    );
    return response;
  }

  /**
   * Switch active workspace session context (WS-A6)
   */
  async switchWorkspace(identifier: string): Promise<SwitchWorkspaceResponse> {
    const response = await post<SwitchWorkspaceResponse>(
      `/api/v1/workspaces/${encodeURIComponent(identifier)}/switch`
    );
    return response;
  }

  /**
   * Retrieve current active workspace context (WS-A6)
   */
  async getCurrentWorkspace(): Promise<CurrentWorkspaceResponse> {
    const response = await get<CurrentWorkspaceResponse>(
      '/api/v1/workspaces/current'
    );
    return response;
  }

  /**
   * List all active workspaces the user belongs to (WS-A6)
   */
  async getUserWorkspaces(): Promise<UserWorkspacesListResponse> {
    const response = await get<UserWorkspacesListResponse>(
      '/api/v1/workspaces/mine'
    );
    return response;
  }
}

/**
 * Canonical helper to construct public workspace join link (Plan B)
 */
export function buildWorkspaceJoinLink(workspaceIdentifier: string, joinCode: string): string {
  const origin = typeof window !== 'undefined' && window.location?.origin ? window.location.origin : '';
  const cleanId = encodeURIComponent((workspaceIdentifier || '').trim());
  const cleanCode = encodeURIComponent((joinCode || '').trim().toUpperCase());
  return `${origin}/workspaces/join?workspace_id=${cleanId}&join_code=${cleanCode}`;
}

export const workspaceService = new WorkspaceService();
export default workspaceService;

