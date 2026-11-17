import { get, post } from '@/api/wrapper';
import type {
  OwnershipTransferResponse,
  OwnershipNominationCreate,
  OwnershipRejectionCreate,
  FormerOwnerChoiceCreate,
  RoleDecisionCreate,
} from '@/types/workspaceTransfer';

export const workspaceTransferService = {
  async getActiveTransfer(workspaceId: string): Promise<OwnershipTransferResponse | null> {
    return await get<OwnershipTransferResponse | null>(`/api/v1/workspaces/${workspaceId}/transfers/active`);
  },

  async nominateOwner(
    workspaceId: string,
    payload: OwnershipNominationCreate
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/nominate`,
      payload
    );
  },

  async acceptTransfer(
    workspaceId: string,
    transferId: string
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/${transferId}/accept`,
      {}
    );
  },

  async rejectTransfer(
    workspaceId: string,
    transferId: string,
    payload?: OwnershipRejectionCreate
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/${transferId}/reject`,
      payload || {}
    );
  },

  async cancelTransfer(
    workspaceId: string,
    transferId: string
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/${transferId}/cancel`,
      {}
    );
  },

  async submitFormerOwnerChoice(
    workspaceId: string,
    transferId: string,
    payload: FormerOwnerChoiceCreate
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/${transferId}/former-owner-choice`,
      payload
    );
  },

  async decideFormerOwnerRole(
    workspaceId: string,
    transferId: string,
    payload: RoleDecisionCreate
  ): Promise<OwnershipTransferResponse> {
    return await post<OwnershipTransferResponse>(
      `/api/v1/workspaces/${workspaceId}/transfers/${transferId}/role-decision`,
      payload
    );
  },
};
