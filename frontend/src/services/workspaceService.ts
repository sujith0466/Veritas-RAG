import { post, patch } from '@/api/wrapper';

export interface Workspace {
  id: string;
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
}

export const workspaceService = new WorkspaceService();
export default workspaceService;

