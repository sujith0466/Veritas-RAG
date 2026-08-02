import { create } from 'zustand';
import { SuspensionReasonCode, Workspace, workspaceService } from '../services/workspaceService';

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
}

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
  }
}));

