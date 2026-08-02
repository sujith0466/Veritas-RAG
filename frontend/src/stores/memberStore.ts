import { create } from 'zustand';
import { memberService } from '@/services/memberService';
import type {
  BulkMemberActionPayload,
  BulkMemberActionResponse,
  WorkspaceMember,
} from '@/types/workspaceMember';

interface MemberState {
  members: WorkspaceMember[];
  total: number;
  isLoading: boolean;
  error: string | null;

  fetchMembers: (
    workspaceId: string,
    params?: {
      search?: string;
      role?: string;
      status?: string;
      page?: number;
      pageSize?: number;
    }
  ) => Promise<void>;
  updateRole: (workspaceId: string, memberId: string, role: string) => Promise<void>;
  suspendMember: (workspaceId: string, memberId: string) => Promise<void>;
  restoreMember: (workspaceId: string, memberId: string) => Promise<void>;
  removeMember: (workspaceId: string, memberId: string) => Promise<void>;
  bulkManage: (
    workspaceId: string,
    payload: BulkMemberActionPayload
  ) => Promise<BulkMemberActionResponse>;
  clearError: () => void;
}

export const useMemberStore = create<MemberState>((set, get) => ({
  members: [],
  total: 0,
  isLoading: false,
  error: null,

  fetchMembers: async (workspaceId, params) => {
    set({ isLoading: true, error: null });
    try {
      const response = await memberService.listMembers(workspaceId, params);
      set({
        members: response.items,
        total: response.total,
        isLoading: false,
      });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to fetch members',
        isLoading: false,
      });
      throw err;
    }
  },

  updateRole: async (workspaceId, memberId, role) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await memberService.updateRole(workspaceId, memberId, { role });
      set((state) => ({
        members: state.members.map((m) => (m.id === memberId ? updated : m)),
        isLoading: false,
      }));
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to update member role',
        isLoading: false,
      });
      throw err;
    }
  },

  suspendMember: async (workspaceId, memberId) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await memberService.suspendMember(workspaceId, memberId);
      set((state) => ({
        members: state.members.map((m) => (m.id === memberId ? updated : m)),
        isLoading: false,
      }));
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to suspend member',
        isLoading: false,
      });
      throw err;
    }
  },

  restoreMember: async (workspaceId, memberId) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await memberService.restoreMember(workspaceId, memberId);
      set((state) => ({
        members: state.members.map((m) => (m.id === memberId ? updated : m)),
        isLoading: false,
      }));
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to restore member',
        isLoading: false,
      });
      throw err;
    }
  },

  removeMember: async (workspaceId, memberId) => {
    set({ isLoading: true, error: null });
    try {
      await memberService.removeMember(workspaceId, memberId);
      set((state) => ({
        members: state.members.filter((m) => m.id !== memberId),
        total: Math.max(0, state.total - 1),
        isLoading: false,
      }));
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to remove member',
        isLoading: false,
      });
      throw err;
    }
  },

  bulkManage: async (workspaceId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await memberService.bulkManage(workspaceId, payload);
      // Refresh member list
      await get().fetchMembers(workspaceId);
      set({ isLoading: false });
      return res;
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || err.message || 'Failed to perform bulk action',
        isLoading: false,
      });
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));
