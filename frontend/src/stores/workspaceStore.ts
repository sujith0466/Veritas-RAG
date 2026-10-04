import { create } from 'zustand';
import { SuspensionReasonCode, Workspace, workspaceService } from '../services/workspaceService';
import { useAuthStore } from './authStore';
import { useChatStore } from './chatStore';
import { useMemberStore } from './memberStore';
import { useFolderStore } from './folderStore';
import { useKnowledgeHealthStore } from './knowledgeHealthStore';
import { appQueryClient } from '../providers/QueryProvider';
import type { SwitchWorkspaceResult, JoinWorkspacePayload, JoinWorkspaceResult } from '@/types';

interface WorkspaceState {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  error: string | null;

  isResolvingWorkspace: boolean;
  createWorkspace: (name: string, description?: string) => Promise<Workspace>;
  joinWorkspace: (payload: JoinWorkspacePayload) => Promise<JoinWorkspaceResult>;
  updateWorkspace: (id: string, expectedUpdatedAt: string, name?: string, description?: string) => Promise<Workspace>;
  setCurrentWorkspace: (workspace: Workspace | null) => void;
  clearError: () => void;
  archiveWorkspace: (id: string, expectedUpdatedAt: string, confirmationName: string, reason?: string) => Promise<Workspace>;
  restoreWorkspace: (id: string, expectedUpdatedAt: string) => Promise<Workspace>;
  suspendWorkspace: (id: string, expectedUpdatedAt: string, confirmationName: string, reasonCode: SuspensionReasonCode, reasonText?: string) => Promise<Workspace>;
  unsuspendWorkspace: (id: string, expectedUpdatedAt: string, reasonText?: string) => Promise<Workspace>;
  switchWorkspace: (identifier: string) => Promise<SwitchWorkspaceResult>;
  fetchCurrentWorkspace: () => Promise<Workspace | null>;
  fetchUserWorkspaces: () => Promise<void>;
  resetWorkspaceResolution: () => void;
}

let latestSwitchSeq = 0;

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  currentWorkspace: null,
  workspaces: [],
  isLoading: false,
  isResolvingWorkspace: false,
  error: null,

  createWorkspace: async (name: string, description?: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.createWorkspace(name, description);
      set((state) => ({
        workspaces: [...state.workspaces, response.data],
        currentWorkspace: response.data,
      }));
      // Authoritatively establish session context as creator (OWNER)
      try {
        await get().switchWorkspace(response.data.id);
      } catch (switchErr) {
        console.warn('Auto-switch after workspace creation fallback:', switchErr);
      }
      set({ isLoading: false });
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to create workspace',
        isLoading: false 
      });
      throw error;
    }
  },

  joinWorkspace: async (payload: JoinWorkspacePayload) => {
    set({ isLoading: true, error: null });
    try {
      const response = await workspaceService.joinWorkspace(payload);
      // If membership was created actively, immediately rotate session to activate context
      if (response.data.status === 'ACTIVE') {
        await get().switchWorkspace(response.data.workspace_id);
      }
      set({ isLoading: false });
      return response.data;
    } catch (error: any) {
      const detail = error.response?.data?.detail || 'Failed to join workspace';
      set({
        error: detail,
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

      const switchData = response?.data || response || {};
      const wsId = switchData.workspace_id || (switchData as any).workspace?.id;
      const wsName = switchData.workspace_name || (switchData as any).workspace?.name;
      const rawRole = switchData.role || (switchData as any).workspace?.role || 'MEMBER';
      const wsPublicId = switchData.workspace_public_id || (switchData as any).workspace?.public_id;
      const wsSlug = switchData.workspace_slug || (switchData as any).workspace?.slug || '';
      const accessToken = switchData.access_token || (switchData as any).workspace?.access_token || '';

      // 1. Update Auth Store with new token and updated user context
      const authStore = useAuthStore.getState();
      if (authStore.user) {
        authStore.setAuth(
          {
            ...authStore.user,
            tenant_id: wsId,
            workspace_id: wsId,
            workspace_name: wsName,
            role: String(rawRole).toLowerCase() as any,
          },
          accessToken
        );
      }

      // 2. Invalidate workspace-scoped state across stores & React Query cache
      useChatStore.getState().clearChatState();
      useMemberStore.getState().clearMemberState();
      useFolderStore.getState().clearFolderState();
      useKnowledgeHealthStore.getState().clearKnowledgeHealthState();
      appQueryClient.clear();

      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('workspace:switched', { detail: switchData }));
      }

      // 3. Update currentWorkspace
      const updatedCurrent: Workspace = {
        id: wsId,
        public_id: wsPublicId || undefined,
        name: wsName,
        slug: wsSlug,
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

  fetchCurrentWorkspace: async (): Promise<Workspace | null> => {
    set({ isResolvingWorkspace: true });
    try {
      const response = await workspaceService.getCurrentWorkspace();
      if (response && response.data) {
        const d = response.data;
        const ws: Workspace = {
          id: d.workspace_id,
          public_id: d.public_id || undefined,
          name: d.name,
          slug: d.slug,
          status: d.status,
          provisioning_status: 'READY',
          updated_at: new Date().toISOString(),
        };
        set({
          currentWorkspace: ws,
          isResolvingWorkspace: false,
        });
        return ws;
      } else {
        set({
          currentWorkspace: null,
          isResolvingWorkspace: false,
        });
        return null;
      }
    } catch (error) {
      console.warn('Failed to fetch current workspace', error);
      set({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      });
      return null;
    }
  },

  resetWorkspaceResolution: () => {
    set({
      currentWorkspace: null,
      isResolvingWorkspace: false,
    });
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

