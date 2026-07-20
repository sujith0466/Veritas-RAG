export interface AnalyticsFilterDTO {
  tenant_id: string
  start_time?: string
  end_time?: string
  interval?: 'hourly' | 'daily' | 'weekly'
  outcome_filter?: string
}

export interface QueryHistoryItemDTO {
  id: string
  tenant_id: string
  correlation_id: string
  query_text: string
  outcome: string
  confidence_score: number | null
  hallucination_score: number | null
  reliability_score: number | null
  retry_attempts: number
  total_duration_ms: number
  is_safe_to_serve: boolean
  created_at: string
}

export interface QueryHistoryListDTO {
  items: QueryHistoryItemDTO[]
  total: number
  page: number
  page_size: number
}

export interface QueryTrendsDTO {
  timestamps: string[]
  query_counts: number[]
  avg_confidence_scores: number[]
  avg_reliability_scores: number[]
}

export interface SuccessRateDTO {
  total_queries: number
  success_count: number
  clarification_count: number
  failure_count: number
  retry_count: number
  success_rate_percentage: number
  avg_retries_per_query: number
}

export interface LatencyAnalyticsDTO {
  p50_ms: number
  p90_ms: number
  p95_ms: number
  p99_ms: number
  avg_ms: number
}

export interface ConfidenceAnalyticsDTO {
  avg_confidence: number
  min_confidence: number
  max_confidence: number
  high_confidence_count: number
  medium_confidence_count: number
  low_confidence_count: number
}

export interface ReliabilityHistoryDTO {
  timestamps: string[]
  scores: number[]
  moving_average_scores: number[]
}

export interface SearchAnalyticsDTO {
  total_searches: number
  avg_dense_candidates: number
  avg_sparse_candidates: number
  avg_merged_unique: number
  avg_retrieval_duration_ms: number
  stage_breakdowns: Record<string, unknown>
}

export interface StageTraceDTO {
  stage_name: string
  duration_ms: number
  status: string
  metadata: Record<string, unknown>
}

export interface RetrievalCandidateTraceDTO {
  chunk_id: string
  document_title: string
  content_snippet: string
  dense_score: number
  sparse_score: number
  rrf_rank: number
  rerank_score: number | null
}

export interface ConfidenceSignalTraceDTO {
  signal_name: string
  weight: number
  score: number
  explanation: string
}

export interface SelfCorrectionTraceDTO {
  attempt_number: number
  trigger_reason: string
  rewritten_query: string | null
  action_taken: string
  duration_ms: number
}

export interface QueryTraceDetailDTO {
  record: QueryHistoryItemDTO
  stage_traces: StageTraceDTO[]
  retrieval_candidates: RetrievalCandidateTraceDTO[]
  confidence_signals: ConfidenceSignalTraceDTO[]
  self_corrections: SelfCorrectionTraceDTO[]
}

export interface QuerySandboxRequestDTO {
  query_text: string
  retrieval_strategy: string
  top_k: number
  confidence_threshold: number
  enable_reranking: boolean
  enable_self_correction: boolean
}

export interface QuerySandboxResponseDTO {
  correlation_id: string
  outcome: string
  final_answer: string
  trace_detail: QueryTraceDetailDTO
}

export type ReportType = 'sla_compliance' | 'reliability_audit' | 'knowledge_health' | 'executive_summary'
export type ReportFormat = 'pdf' | 'json'

export interface ReportExportRequestDTO {
  report_type: ReportType
  start_date?: string
  end_date?: string
  tenant_id?: string
  include_stage_breakdown?: boolean
  include_anomalies?: boolean
  format?: ReportFormat
}

export interface ReportMetadataDTO {
  report_id: string
  report_type: string
  title: string
  generated_at: string
  date_range_label: string
  status: string
  download_url: string
  summary_metrics: Record<string, unknown>
}

