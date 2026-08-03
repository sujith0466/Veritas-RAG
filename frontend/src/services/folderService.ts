import { get, post, patch, del } from '../api/wrapper';

export interface Folder {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  depth: number;
  path: string;
  document_count: number;
  version: number;
  created_at: string;
  updated_at: string;
  is_deleted: boolean;
  cascade_status?: string | null;
  purge_at?: string | null;
  purge_status?: string | null;
  purge_started_at?: string | null;
  purge_completed_at?: string | null;
}

export interface FolderPurgeStatus {
  folder_id: string;
  is_deleted: boolean;
  deleted_at: string | null;
  purge_at: string | null;
  purge_status: string | null;
  purge_started_at: string | null;
  purge_completed_at: string | null;
  days_until_purge: number | null;
}

export interface FolderStats {
  child_folder_count: number;
  document_count: number;
  total_descendant_folder_count: number;
}

export const folderService = {
  createFolder: (workspaceId: string, name: string, parentId: string | null = null) => {
    return post<Folder>(`/workspaces/${workspaceId}/folders`, {
      name,
      parent_id: parentId,
    });
  },

  renameFolder: (workspaceId: string, folderId: string, name: string, version: number) => {
    return patch<Folder>(`/workspaces/${workspaceId}/folders/${folderId}`, {
      name,
      version,
    });
  },

  softDeleteFolder: (workspaceId: string, folderId: string, version: number) => {
    return del<{ status: string; folder_id: string; cascade_pending: boolean; worker_task_id: string | null }>(
      `/workspaces/${workspaceId}/folders/${folderId}?version=${version}`
    );
  },

  restoreFolder: (workspaceId: string, folderId: string) => {
    return post<{ status: string; folder_id: string; cascade_pending: boolean; worker_task_id: string | null }>(
      `/workspaces/${workspaceId}/folders/${folderId}/restore`
    );
  },

  getFolderStats: (workspaceId: string, folderId: string) => {
    return get<FolderStats>(`/workspaces/${workspaceId}/folders/${folderId}/stats`);
  },

  moveFolder: (workspaceId: string, folderId: string, targetParentId: string | null, version: number) => {
    return post<{ status: string; worker_task_id: string | null; cascade_pending: boolean }>(
      `/workspaces/${workspaceId}/folders/${folderId}/move`,
      {
        target_parent_id: targetParentId,
        version,
      }
    );
  },

  earlyHardDeleteFolder: (workspaceId: string, folderId: string, confirmationName: string, reason?: string) => {
    return del<{ status: string; purge_at: string; worker_task_id: string | null }>(
      `/workspaces/${workspaceId}/folders/${folderId}/hard-delete`,
      {
        data: {
          confirmation_name: confirmationName,
          reason,
        }
      }
    );
  },

  getPurgeStatus: (workspaceId: string, folderId: string) => {
    return get<FolderPurgeStatus>(`/workspaces/${workspaceId}/folders/${folderId}/purge-status`);
  },
};
