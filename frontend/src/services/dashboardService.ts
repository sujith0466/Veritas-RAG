import { get } from '@/api/wrapper'
import type {
  CommandCenterDTO,
  ExecutiveDashboardDTO,
  KnowledgeIntelligenceSummaryDTO,
  QueryExecutionLedgerDTO,
  QueryExecutionTraceDTO,
} from '@/types'

export const dashboardService = {
  getCommandCenter: async (timeWindow: string = '24h'): Promise<CommandCenterDTO> => {
    return get<CommandCenterDTO>(`/dashboard/command-center?time_window=${encodeURIComponent(timeWindow)}`)
  },

  getExecutions: async (params: {
    timeWindow?: string
    limit?: number
    offset?: number
    status?: string
    search?: string
    minReliability?: number
  } = {}): Promise<QueryExecutionLedgerDTO> => {
    const query = new URLSearchParams()
    if (params.timeWindow) query.set('time_window', params.timeWindow)
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    if (params.offset !== undefined) query.set('offset', String(params.offset))
    if (params.status && params.status !== 'ALL') query.set('status', params.status)
    if (params.search) query.set('search', params.search)
    if (params.minReliability !== undefined) query.set('min_reliability', String(params.minReliability))

    const qs = query.toString()
    return get<QueryExecutionLedgerDTO>(`/dashboard/executions${qs ? `?${qs}` : ''}`)
  },

  getExecutionTrace: async (queryId: string): Promise<QueryExecutionTraceDTO> => {
    return get<QueryExecutionTraceDTO>(`/dashboard/executions/${encodeURIComponent(queryId)}/trace`)
  },

  getExecutiveDashboard: async (timeWindow: string = '24h'): Promise<ExecutiveDashboardDTO> => {
    return get<ExecutiveDashboardDTO>(`/dashboard/executive?time_window=${encodeURIComponent(timeWindow)}`)
  },

  getKnowledgeIntelligenceSummary: async (): Promise<KnowledgeIntelligenceSummaryDTO> => {
    return get<KnowledgeIntelligenceSummaryDTO>('/dashboard/knowledge-intelligence')
  },
}

