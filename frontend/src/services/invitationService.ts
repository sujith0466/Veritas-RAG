import { get, post, del } from '@/api/wrapper';
import type {
  ResendInvitationPayload,
  SendInvitationPayload,
  VerifyInvitationData,
  WorkspaceInvitation,
  WorkspaceInvitationListResult,
} from '@/types/workspaceInvitation';

class InvitationService {
  /**
   * Send a new workspace invitation.
   */
  async sendInvitation(
    workspaceId: string,
    payload: SendInvitationPayload
  ): Promise<WorkspaceInvitation> {
    return post<WorkspaceInvitation>(
      `/api/v1/workspaces/${workspaceId}/invitations`,
      payload
    );
  }

  /**
   * List paginated workspace invitations.
   */
  async listInvitations(
    workspaceId: string,
    status?: string,
    page: number = 1,
    pageSize: number = 50
  ): Promise<WorkspaceInvitationListResult> {
    const params: Record<string, unknown> = {
      page,
      page_size: pageSize,
    };
    if (status) {
      params.status = status;
    }
    return get<WorkspaceInvitationListResult>(
      `/api/v1/workspaces/${workspaceId}/invitations`,
      params
    );
  }

  /**
   * Resend an invitation with token rotation.
   */
  async resendInvitation(
    workspaceId: string,
    invitationId: string,
    payload?: ResendInvitationPayload
  ): Promise<WorkspaceInvitation> {
    return post<WorkspaceInvitation>(
      `/api/v1/workspaces/${workspaceId}/invitations/${invitationId}/resend`,
      payload || {}
    );
  }

  /**
   * Revoke an active invitation.
   */
  async revokeInvitation(
    workspaceId: string,
    invitationId: string
  ): Promise<WorkspaceInvitation> {
    return del<WorkspaceInvitation>(
      `/api/v1/workspaces/${workspaceId}/invitations/${invitationId}`
    );
  }

  /**
   * Verify invitation token metadata (public / preview page).
   */
  async verifyInvitation(token: string): Promise<VerifyInvitationData> {
    return get<VerifyInvitationData>('/api/v1/invitations/verify', { token });
  }

  /**
   * Accept an invitation using raw token.
   */
  async acceptInvitation(
    payload: { token: string }
  ): Promise<{ workspace_id: string; workspace_name: string; role: string; member_id: string }> {
    return post<{ workspace_id: string; workspace_name: string; role: string; member_id: string }>(
      '/api/v1/invitations/accept',
      payload
    );
  }
}

export const invitationService = new InvitationService();
export default invitationService;
