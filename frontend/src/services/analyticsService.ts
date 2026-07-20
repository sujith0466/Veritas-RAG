import { get, post } from '@/api/wrapper'
import type {
  ConfidenceAnalyticsDTO,
  LatencyAnalyticsDTO,
  QueryHistoryListDTO,
  QueryTrendsDTO,
  ReliabilityHistoryDTO,
  SearchAnalyticsDTO,
  SuccessRateDTO,
  QueryTraceDetailDTO,
  QuerySandboxRequestDTO,
  QuerySandboxResponseDTO,
  ReportExportRequestDTO,
  ReportMetadataDTO,
} from '@/types'

export const analyticsService = {
  async getQueryHistory(
    page = 1,
    pageSize = 50,
    outcome?: string,
    startTime?: string,
    endTime?: string,
  ): Promise<QueryHistoryListDTO> {
    const params: Record<string, unknown> = { page, page_size: pageSize }
    if (outcome) params.outcome = outcome
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<QueryHistoryListDTO>('/analytics/history', params)
  },

  async getSuccessRate(startTime?: string, endTime?: string): Promise<SuccessRateDTO> {
    const params: Record<string, unknown> = {}
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<SuccessRateDTO>('/analytics/success-rate', params)
  },

  async getLatencyAnalytics(startTime?: string, endTime?: string): Promise<LatencyAnalyticsDTO> {
    const params: Record<string, unknown> = {}
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<LatencyAnalyticsDTO>('/analytics/latency', params)
  },

  async getConfidenceAnalytics(startTime?: string, endTime?: string): Promise<ConfidenceAnalyticsDTO> {
    const params: Record<string, unknown> = {}
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<ConfidenceAnalyticsDTO>('/analytics/confidence', params)
  },

  async getQueryTrends(
    interval: 'hourly' | 'daily' | 'weekly' = 'daily',
    startTime?: string,
    endTime?: string,
  ): Promise<QueryTrendsDTO> {
    const params: Record<string, unknown> = { interval }
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<QueryTrendsDTO>('/analytics/trends', params)
  },

  async getReliabilityHistory(
    interval: 'hourly' | 'daily' | 'weekly' = 'daily',
    startTime?: string,
    endTime?: string,
  ): Promise<ReliabilityHistoryDTO> {
    const params: Record<string, unknown> = { interval }
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    return get<ReliabilityHistoryDTO>('/analytics/reliability-history', params)
  },

  async getSearchAnalytics(): Promise<SearchAnalyticsDTO> {
    return get<SearchAnalyticsDTO>('/analytics/search')
  },

  async getQueryTraceDetail(correlationId: string): Promise<QueryTraceDetailDTO> {
    return get<QueryTraceDetailDTO>(`/analytics/trace/${correlationId}`)
  },

  async executeSandboxQuery(request: QuerySandboxRequestDTO): Promise<QuerySandboxResponseDTO> {
    return post<QuerySandboxResponseDTO>('/analytics/sandbox/execute', request)
  },

  async exportReport(request: ReportExportRequestDTO): Promise<ReportMetadataDTO> {
    return post<ReportMetadataDTO>('/analytics/reports/export', request)
  },

  async listGeneratedReports(): Promise<ReportMetadataDTO[]> {
    return get<ReportMetadataDTO[]>('/analytics/reports/history')
  },
}

