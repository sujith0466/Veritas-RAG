import { create } from 'zustand';
import { SuspensionReasonCode, Workspace, workspaceService } from '../services/workspaceService';
import { useAuthStore } from './authStore';
import { useChatStore } from './chatStore';
import type { SwitchWorkspaceResult } from '@/types';

interface WorkspaceState {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  error: string | null;

  createWorkspace: (name: string, description?: string) => Promise<Workspace>;
  updateWorkspace: (id: string, expectedUpdatedAt: string, name?: string, description?: string) => Promise<Workspace>;
  setCurrentWorkspace: (workspace: Workspace | null) => void;
  clearError: () => void;
  archiveWorkspace: (id: string, expectedUpdatedAt: string, confirmationName: string, reason?: string) => Promise<Workspace>;
  restoreWorkspace: (id: string, expectedUpdatedAt: string) => Promise<Workspace>;
  suspendWorkspace: (id: string, expectedUpdatedAt: string, confirmationName: string, reasonCode: SuspensionReasonCode, reasonText?: string) => Promise<Workspace>;
  unsuspendWorkspace: (id: string, expectedUpdatedAt: string, reasonText?: string) => Promise<Workspace>;
  switchWorkspace: (identifier: string) => Promise<SwitchWorkspaceResult>;
  fetchCurrentWorkspace: () => Promise<void>;
  fetchUserWorkspaces: () => Promise<void>;
}

let latestSwitchSeq = 0;

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  currentWorkspace: null,
  workspaces: [],
  isLoading: false,
  error: null,

  createWorkspace: async (name: string, description?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.createWorkspace(name, description);
      set((state) => ({
        workspaces: [...state.workspaces, response.data],
        currentWorkspace: response.data,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to create workspace',
        isLoading: false 
      });
      throw error;
    }
  },

  setCurrentWorkspace: (workspace) => set({ currentWorkspace: workspace }),
  clearError: () => set({ error: null }),
  
  updateWorkspace: async (id: string, expectedUpdatedAt: string, name?: string, description?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.updateWorkspace(id, expectedUpdatedAt, name, description);
      set((state) => ({
        workspaces: state.workspaces.map(w => w.id === id ? response.data : w),
        currentWorkspace: state.currentWorkspace?.id === id ? response.data : state.currentWorkspace,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to update workspace';
      set({ 
        error: detail,
        isLoading: false 
      });
      throw error;
    }
  },

  archiveWorkspace: async (id: string, expectedUpdatedAt: string, confirmationName: string, reason?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.archiveWorkspace(id, expectedUpdatedAt, confirmationName, reason);
      set((state) => ({
        workspaces: state.workspaces.map(w => w.id === id ? response.data : w),
        currentWorkspace: state.currentWorkspace?.id === id ? response.data : state.currentWorkspace,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to archive workspace';
      set({ 
        error: detail,
        isLoading: false 
      });
      throw error;
    }
  },

  restoreWorkspace: async (id: string, expectedUpdatedAt: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.restoreWorkspace(id, expectedUpdatedAt);
      set((state) => ({
        workspaces: state.workspaces.map(w => w.id === id ? response.data : w),
        currentWorkspace: state.currentWorkspace?.id === id ? response.data : state.currentWorkspace,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to restore workspace';
      set({ 
        error: detail,
        isLoading: false 
      });
      throw error;
    }
  },

  suspendWorkspace: async (id: string, expectedUpdatedAt: string, confirmationName: string, reasonCode: SuspensionReasonCode, reasonText?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.suspendWorkspace(id, expectedUpdatedAt, confirmationName, reasonCode, reasonText);
      set((state) => ({
        workspaces: state.workspaces.map(w => w.id === id ? response.data : w),
        currentWorkspace: state.currentWorkspace?.id === id ? response.data : state.currentWorkspace,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to suspend workspace';
      set({ 
        error: detail,
        isLoading: false 
      });
      throw error;
    }
  },

  unsuspendWorkspace: async (id: string, expectedUpdatedAt: string, reasonText?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.unsuspendWorkspace(id, expectedUpdatedAt, reasonText);
      set((state) => ({
        workspaces: state.workspaces.map(w => w.id === id ? response.data : w),
        currentWorkspace: state.currentWorkspace?.id === id ? response.data : state.currentWorkspace,
        isLoading: false
      }));
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to unsuspend workspace';
      set({ 
        error: detail,
        isLoading: false 
      });
      throw error;
    }
  },

  switchWorkspace: async (identifier: string) => {
    set({ isLoading: true, error: null });
    const switchSeq = ++latestSwitchSeq;
    try {
      const response = await workspaceService.switchWorkspace(identifier);
      if (switchSeq < latestSwitchSeq) {
        // Obsoleted by a concurrent newer switch request
        return response.data;
      }

      const switchData = response.data;

      // 1. Update Auth Store with new token and updated user context
      const authStore = useAuthStore.getState();
      if (authStore.user) {
        authStore.setAuth(
          {
            ...authStore.user,
            tenant_id: switchData.workspace_id,
            workspace_id: switchData.workspace_id,
            workspace_name: switchData.workspace_name,
            role: switchData.role.toLowerCase() as any,
          },
          switchData.access_token
        );
      }

      // 2. Invalidate workspace-scoped chat state
      useChatStore.getState().clearChatState();

      // 3. Update currentWorkspace
      const updatedCurrent: Workspace = {
        id: switchData.workspace_id,
        public_id: switchData.workspace_public_id || undefined,
        name: switchData.workspace_name,
        slug: switchData.workspace_slug || '',
        status: 'ACTIVE',
        provisioning_status: 'READY',
        updated_at: new Date().toISOString(),
      };

      set({
        currentWorkspace: updatedCurrent,
        isLoading: false,
        error: null,
      });

      return switchData;
    } catch (error: any) {
      if (switchSeq >= latestSwitchSeq) {
        const detail = error.response?.data?.detail || error.message || 'Failed to switch workspace';
        set({
          error: detail,
          isLoading: false,
        });
      }
      throw error;
    }
  },

  fetchCurrentWorkspace: async () => {
    try {
      const response = await workspaceService.getCurrentWorkspace();
      if (response.data) {
        const d = response.data;
        set({
          currentWorkspace: {
            id: d.workspace_id,
            public_id: d.public_id || undefined,
            name: d.name,
            slug: d.slug,
            status: d.status,
            provisioning_status: 'READY',
            updated_at: new Date().toISOString(),
          },
        });
      }
    } catch (error) {
      console.warn('Failed to fetch current workspace', error);
    }
  },

  fetchUserWorkspaces: async () => {
    try {
      const response = await workspaceService.getUserWorkspaces();
      if (response.items) {
        const mappedWorkspaces: Workspace[] = response.items.map((item) => ({
          id: item.workspace_id,
          public_id: item.public_id || undefined,
          name: item.name,
          slug: item.slug,
          status: item.status,
          provisioning_status: 'READY',
          updated_at: new Date().toISOString(),
        }));
        set({ workspaces: mappedWorkspaces });
      }
    } catch (error) {
      console.warn('Failed to fetch user workspaces', error);
    }
  },
}));

