import { get, put } from '@/api/wrapper'

export interface AuditLog {
  id: string
  tenant_id: string
  user_id?: string
  action: string
  resource_type: string
  resource_id?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  details: Record<string, any>
  created_at: string
}

export interface AuditLogPagination {
  page: number
  size: number
  total_elements: number
  total_pages: number
}

export interface AuditLogResponse {
  items: AuditLog[]
  pagination: AuditLogPagination
}

export interface AuditLogFilters {
  query?: string
  action?: string
  start_date?: string
  end_date?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
}

export interface TenantQuota {
  tenant_id: string
  monthly_token_limit: number
  monthly_budget_usd: number
  warning_threshold_pct: number
  is_hard_enforced: boolean
  remaining_tokens: number
  remaining_budget_usd: number
}

export interface WorkspaceUsage {
  workspace_id: string
  billing_period_start: string
  used_tokens: number
  used_queries: number
  monthly_token_limit: number
  monthly_budget_usd: number
  warning_threshold_pct: number
  is_hard_enforced: boolean
  remaining_tokens: number
  remaining_budget_usd: number
  is_warning: boolean
  is_exceeded: boolean
}

export interface WorkspaceSummary {
  id: string
  name: string
  member_count: number
  total_queries: number
}

export interface WorkspaceUserQuota {
  id?: string
  workspace_id: string
  user_id: string
  monthly_token_budget: number | null
  is_hard_enforced: boolean
  warning_threshold_pct: number
  user_email?: string
  user_display_name?: string
  member_role?: string
  used_tokens: number
  used_queries: number
  workspace_token_limit: number
}

export interface WorkspaceUserQuotaUpdate {
  monthly_token_budget: number | null
  is_hard_enforced?: boolean
  warning_threshold_pct?: number
}

export const adminService = {
  // F12.6 Audit Logs
  getAuditLogs: async (
    page = 1,
    pageSize = 50,
    filters?: AuditLogFilters
  ): Promise<AuditLogResponse> => {
    const params: Record<string, any> = { page, page_size: pageSize }
    if (filters?.query) params.query = filters.query
    if (filters?.action) params.action = filters.action
    if (filters?.start_date) params.start_date = filters.start_date
    if (filters?.end_date) params.end_date = filters.end_date
    return get<AuditLogResponse>('/api/v1/audit-logs', params)
  },

  // F12.5 Quota Management
  getQuota: async (tenantId: string): Promise<TenantQuota> => {
    return get<TenantQuota>(`/analytics/v1/quotas/${tenantId}`)
  },

  updateQuota: async (tenantId: string, payload: Partial<TenantQuota>): Promise<TenantQuota> => {
    return put<TenantQuota>(`/analytics/v1/quotas/${tenantId}`, payload)
  },

  // F13.2 Workspace Usage
  getWorkspaceUsage: async (workspaceId: string): Promise<WorkspaceUsage> => {
    return get<WorkspaceUsage>(`/analytics/v1/workspace-usage/${workspaceId}`)
  },

  // WS-B9: User-level Quotas and Usage
  getUserQuotas: async (workspaceId: string): Promise<WorkspaceUserQuota[]> => {
    return get<WorkspaceUserQuota[]>(`/analytics/v1/workspace-user-quotas/${workspaceId}`)
  },

  getMyUserQuota: async (workspaceId: string): Promise<WorkspaceUserQuota> => {
    return get<WorkspaceUserQuota>(`/analytics/v1/workspace-user-quotas/${workspaceId}/me`)
  },

  updateUserQuota: async (
    workspaceId: string,
    userId: string,
    payload: WorkspaceUserQuotaUpdate
  ): Promise<WorkspaceUserQuota> => {
    return put<WorkspaceUserQuota>(`/analytics/v1/workspace-user-quotas/${workspaceId}/${userId}`, payload)
  },

  // F12.2 Platform Admin
  getGlobalWorkspaces: async (page = 1, pageSize = 50): Promise<PaginatedResponse<WorkspaceSummary>> => {
    return get<PaginatedResponse<WorkspaceSummary>>('/api/v1/platform-admin/workspaces', { page, page_size: pageSize })
  }
}

