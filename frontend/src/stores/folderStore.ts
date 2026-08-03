import { create } from 'zustand';
import { folderService, Folder, FolderStats } from '../services/folderService';

interface FolderState {
  folders: Folder[];
  isLoading: boolean;
  error: string | null;

  createFolder: (workspaceId: string, name: string, parentId?: string | null) => Promise<Folder>;
  renameFolder: (workspaceId: string, folderId: string, name: string, version: number) => Promise<Folder>;
  softDeleteFolder: (workspaceId: string, folderId: string, version: number) => Promise<void>;
  restoreFolder: (workspaceId: string, folderId: string) => Promise<void>;
  getFolderStats: (workspaceId: string, folderId: string) => Promise<FolderStats>;
  moveFolder: (workspaceId: string, folderId: string, targetParentId: string | null, version: number) => Promise<void>;
  earlyHardDeleteFolder: (workspaceId: string, folderId: string, confirmationName: string) => Promise<void>;
  clearError: () => void;
}

export const useFolderStore = create<FolderState>((set) => ({
  folders: [],
  isLoading: false,
  error: null,

  createFolder: async (workspaceId: string, name: string, parentId: string | null = null) => {
    set({ isLoading: true, error: null });
    try {
      const response = await folderService.createFolder(workspaceId, name, parentId);
      set((state) => ({
        folders: [...state.folders, response],
        isLoading: false
      }));
      return response;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to create folder',
        isLoading: false 
      });
      throw error;
    }
  },

  renameFolder: async (workspaceId: string, folderId: string, name: string, version: number) => {
    set({ isLoading: true, error: null });
    try {
      const response = await folderService.renameFolder(workspaceId, folderId, name, version);
      set((state) => ({
        folders: state.folders.map(f => f.id === folderId ? response : f),
        isLoading: false
      }));
      return response;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to rename folder',
        isLoading: false 
      });
      throw error;
    }
  },

  softDeleteFolder: async (workspaceId: string, folderId: string, version: number) => {
    set({ isLoading: true, error: null });
    try {
      await folderService.softDeleteFolder(workspaceId, folderId, version);
      set((state) => ({
        folders: state.folders.filter(f => f.id !== folderId),
        isLoading: false
      }));
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to delete folder',
        isLoading: false 
      });
      throw error;
    }
  },

  restoreFolder: async (workspaceId: string, folderId: string) => {
    set({ isLoading: true, error: null });
    try {
      await folderService.restoreFolder(workspaceId, folderId);
      set({ isLoading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to restore folder',
        isLoading: false 
      });
      throw error;
    }
  },

  getFolderStats: async (workspaceId: string, folderId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await folderService.getFolderStats(workspaceId, folderId);
      set({ isLoading: false });
      return response;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to get folder stats',
        isLoading: false 
      });
      throw error;
    }
  },


  moveFolder: async (workspaceId: string, folderId: string, targetParentId: string | null, version: number) => {
    set({ isLoading: true, error: null });
    try {
      const response = await folderService.moveFolder(workspaceId, folderId, targetParentId, version);
      set((state) => ({
        // We optimistically mark it as cascade_pending if the API returns that
        folders: state.folders.map(f => f.id === folderId ? { ...f, cascade_status: response.cascade_pending ? 'move_pending' : null, parent_id: targetParentId } : f),
        isLoading: false
      }));
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to move folder',
        isLoading: false 
      });
      throw error;
    }
  },

  earlyHardDeleteFolder: async (workspaceId: string, folderId: string, confirmationName: string) => {
    set({ isLoading: true, error: null });
    try {
      await folderService.earlyHardDeleteFolder(workspaceId, folderId, confirmationName);
      set({ isLoading: false });
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'Failed to hard delete folder',
        isLoading: false 
      });
      throw error;
    }
  },
  clearError: () => set({ error: null }),
}));
