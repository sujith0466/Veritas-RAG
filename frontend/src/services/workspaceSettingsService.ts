import { get, patch, post } from '@/api/wrapper'

export interface WorkspaceSettingsData {
  workspace_id: string
  settings: {
    general?: {
      default_language?: string
      timezone?: string
      date_format?: string
      retention_days?: number
      [key: string]: any
    }
    security?: Record<string, any>
    ai?: Record<string, any>
    rag?: Record<string, any>
    storage?: Record<string, any>
    notifications?: Record<string, any>
    integrations?: Record<string, any>
    limits?: Record<string, any>
    branding?: Record<string, any>
    api?: Record<string, any>
    staleness?: Record<string, any>
    custom_extensions?: Record<string, any>
    [category: string]: any
  }
  schema_version: number
  version: number
  settings_hash: string
  updated_at: string
}

export interface WorkspaceSettingsResponse {
  success: boolean
  data: WorkspaceSettingsData
}

class WorkspaceSettingsService {
  /**
   * Retrieve full validated workspace settings document.
   */
  async getSettings(workspaceId: string): Promise<WorkspaceSettingsResponse> {
    return get<WorkspaceSettingsResponse>(`/api/v1/workspaces/${workspaceId}/settings`)
  }

  /**
   * Deep merge patch into workspace settings with optimistic concurrency lock.
   */
  async patchSettings(
    workspaceId: string,
    expectedUpdatedAt: string,
    settings: Record<string, any>
  ): Promise<WorkspaceSettingsResponse> {
    return patch<WorkspaceSettingsResponse>(`/api/v1/workspaces/${workspaceId}/settings`, {
      expected_updated_at: expectedUpdatedAt,
      settings,
    })
  }

  /**
   * Reset workspace settings to defaults.
   */
  async resetSettings(
    workspaceId: string,
    expectedUpdatedAt: string,
    category?: string
  ): Promise<WorkspaceSettingsResponse> {
    return post<WorkspaceSettingsResponse>(`/api/v1/workspaces/${workspaceId}/settings/reset`, {
      expected_updated_at: expectedUpdatedAt,
      category: category || null,
    })
  }

  /**
   * Export complete workspace configuration document.
   */
  async exportSettings(workspaceId: string): Promise<WorkspaceSettingsResponse> {
    return get<WorkspaceSettingsResponse>(`/api/v1/workspaces/${workspaceId}/settings/export`)
  }
}

export const workspaceSettingsService = new WorkspaceSettingsService()
