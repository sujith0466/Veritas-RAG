import { get, post, patch, del } from '@/api/wrapper';
import type {
  BulkMemberActionPayload,
  BulkMemberActionResponse,
  UpdateRolePayload,
  WorkspaceMember,
  WorkspaceMemberListResult,
} from '@/types/workspaceMember';

class MemberService {
  /**
   * List paginated members in a workspace with optional filtering.
   */
  async listMembers(
    workspaceId: string,
    params?: {
      search?: string;
      role?: string;
      status?: string;
      cursor?: string;
      page?: number;
      pageSize?: number;
    }
  ): Promise<WorkspaceMemberListResult> {
    const queryParams: Record<string, unknown> = {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 50,
    };
    if (params?.search) queryParams.search = params.search;
    if (params?.role) queryParams.role = params.role;
    if (params?.status) queryParams.status = params.status;
    if (params?.cursor) queryParams.cursor = params.cursor;

    return get<WorkspaceMemberListResult>(
      `/api/v1/workspaces/${workspaceId}/members`,
      queryParams
    );
  }

  /**
   * Get single member details.
   */
  async getMember(workspaceId: string, memberId: string): Promise<WorkspaceMember> {
    return get<WorkspaceMember>(`/api/v1/workspaces/${workspaceId}/members/${memberId}`);
  }

  /**
   * Update member role.
   */
  async updateRole(
    workspaceId: string,
    memberId: string,
    payload: UpdateRolePayload
  ): Promise<WorkspaceMember> {
    return patch<WorkspaceMember>(
      `/api/v1/workspaces/${workspaceId}/members/${memberId}/role`,
      payload
    );
  }

  /**
   * Suspend a member.
   */
  async suspendMember(workspaceId: string, memberId: string): Promise<WorkspaceMember> {
    return post<WorkspaceMember>(
      `/api/v1/workspaces/${workspaceId}/members/${memberId}/suspend`,
      {}
    );
  }

  /**
   * Restore a suspended member.
   */
  async restoreMember(workspaceId: string, memberId: string): Promise<WorkspaceMember> {
    return post<WorkspaceMember>(
      `/api/v1/workspaces/${workspaceId}/members/${memberId}/restore`,
      {}
    );
  }

  /**
   * Soft remove a member from workspace.
   */
  async removeMember(workspaceId: string, memberId: string): Promise<WorkspaceMember> {
    return del<WorkspaceMember>(
      `/api/v1/workspaces/${workspaceId}/members/${memberId}`
    );
  }

  /**
   * Execute bulk action across members.
   */
  async bulkManage(
    workspaceId: string,
    payload: BulkMemberActionPayload
  ): Promise<BulkMemberActionResponse> {
    return post<BulkMemberActionResponse>(
      `/api/v1/workspaces/${workspaceId}/members/bulk`,
      payload
    );
  }
}

export const memberService = new MemberService();
export default memberService;
