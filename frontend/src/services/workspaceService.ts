import { get, post, patch } from '@/api/wrapper';
import type {
  WorkspacePreviewResponse,
  JoinCodeSettings,
  JoinCodeSettingsPatchPayload,
  JoinCodeGenerateResponse,
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
   * Resolve public workspace preview by Workspace ID or slug
   */
  async lookupWorkspace(identifier: string): Promise<WorkspacePreviewResponse> {
    const response = await get<WorkspacePreviewResponse>(
      `/api/v1/workspaces/lookup?identifier=${encodeURIComponent(identifier)}`
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
    const response = await post<JoinCodeGenerateResponse>(
      `/api/v1/workspaces/${workspaceId}/join-code/generate`,
      params
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
    const response = await post<JoinCodeGenerateResponse>(
      `/api/v1/workspaces/${workspaceId}/join-code/regenerate`,
      params
    );
    return response;
  }
}

export const workspaceService = new WorkspaceService();
export default workspaceService;

