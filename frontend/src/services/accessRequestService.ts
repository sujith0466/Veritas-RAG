import { get, post } from '@/api/wrapper';

export interface AccessRequestData {
  id: string;
  workspace_id: string;
  user_id: string;
  request_type: 'ROLE_ELEVATION' | 'JOIN_APPROVAL';
  current_role: string | null;
  requested_role: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  reason: string | null;
  reviewed_by_id: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  user_email?: string | null;
  user_display_name?: string | null;
}

export interface AccessRequestResponse {
  success: boolean;
  request: AccessRequestData;
}

export interface AccessRequestListResponse {
  items: AccessRequestData[];
  total: number;
  skip: number;
  limit: number;
}

export interface CreateAccessRequestPayload {
  request_type: 'ROLE_ELEVATION' | 'JOIN_APPROVAL';
  requested_role: string;
  reason?: string;
}

export interface RejectAccessRequestPayload {
  rejection_reason?: string;
}

class AccessRequestService {
  async submitRequest(
    workspaceId: string,
    payload: CreateAccessRequestPayload
  ): Promise<AccessRequestResponse> {
    return post<AccessRequestResponse>(
      `/api/v1/workspaces/${workspaceId}/access-requests`,
      payload
    );
  }

  async listRequests(
    workspaceId: string,
    params?: { status?: string; skip?: number; limit?: number }
  ): Promise<AccessRequestListResponse> {
    return get<AccessRequestListResponse>(
      `/api/v1/workspaces/${workspaceId}/access-requests`,
      params
    );
  }

  async approveRequest(
    workspaceId: string,
    requestId: string
  ): Promise<AccessRequestResponse> {
    return post<AccessRequestResponse>(
      `/api/v1/workspaces/${workspaceId}/access-requests/${requestId}/approve`,
      {}
    );
  }

  async rejectRequest(
    workspaceId: string,
    requestId: string,
    payload?: RejectAccessRequestPayload
  ): Promise<AccessRequestResponse> {
    return post<AccessRequestResponse>(
      `/api/v1/workspaces/${workspaceId}/access-requests/${requestId}/reject`,
      payload || {}
    );
  }
}

export const accessRequestService = new AccessRequestService();
export default accessRequestService;
