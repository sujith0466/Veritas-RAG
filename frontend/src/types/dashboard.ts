/**
 * Data transfer types for Dashboard & Knowledge Intelligence.
 */

export interface KnowledgeStageMetricDTO {
  stage_name: string
  avg_duration_ms: number
  success_count: number
  failure_count: number
}

export interface KnowledgeIntelligenceSummaryDTO {
  tenant_id: string
  total_documents: number
  processed_documents: number
  failed_documents: number
  validation_pass_rate: number
  total_chunks: number
  avg_tokens_per_chunk: number
  chunk_strategy_counts: Record<string, number>
  total_embeddings: number
  total_embedding_tokens_consumed: number
  active_embedding_provider: string
  active_embedding_model: string
  vector_collections_count: number
  vector_cluster_status: string
  total_vector_points: number
  stage_latencies: {
    stage_name: string
    avg_duration_ms: number
    success_count: number
    failure_count: number
  }[]
  recent_health_scans: {
    id: string
    scan_type: string
    status: string
    created_at: string | null
    orphans_found: number
    orphans_purged: number
    parity_status: string
  }[]
  parity_audit_status: string
}

export interface ExecutiveDashboardActivityDTO {
  id: string
  timestamp: string
  event_type: string
  title: string
  description: string
  status: string
  confidence_score: number | null
  duration_ms: number | null
}

export interface ExecutiveDashboardAlertDTO {
  id: string
  timestamp: string
  alert_type: string
  severity: string
  query_snippet: string
  reason: string
}

export interface ExecutiveDashboardDTO {
  tenant_id: string
  active_tenants: number
  time_window?: string
  total_queries?: number
  total_queries_last_24h: number
  avg_reliability_score: number | null
  avg_confidence_score: number | null
  avg_latency_ms?: number | null
  blocked_hallucinations_last_24h: number
  clarification_rate: number
  system_status: string
  recent_activity: ExecutiveDashboardActivityDTO[]
  security_alerts: ExecutiveDashboardAlertDTO[]
}

export interface CommandHealthComponentDTO {
  name: string
  status: string
  latency_ms: number | null
  detail: string | null
}

export interface CommandSystemHealthDTO {
  status: string
  components: CommandHealthComponentDTO[]
}

export interface CommandKpisDTO {
  total_queries: number
  avg_reliability_score: number | null
  avg_confidence_score: number | null
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  self_correction_rate: number
  clarification_rate: number
  hallucination_prevention_count: number
  active_tenants: number
  active_workspaces: number
}

export interface CommandReliabilityTrendPointDTO {
  timestamp: string
  reliability: number
  query_count: number
}

export interface CommandLatencyPercentilesDTO {
  p50_ms: number | null
  p90_ms: number | null
  p95_ms: number | null
  p99_ms: number | null
  avg_ms: number | null
}

export interface CommandOutcomesBreakdownDTO {
  success_count: number
  aborted_hallucination_count: number
  aborted_low_confidence_count: number
  clarification_count: number
  no_relevant_chunks_count: number
  policy_violation_count: number
  total_count: number
}

export interface CommandKnowledgeHealthDTO {
  total_documents: number
  processed_documents: number
  failed_documents: number
  total_chunks: number
  total_embeddings: number
  pending_jobs: number
  failed_jobs: number
  vector_status: string
}

export interface CommandCenterDTO {
  tenant_id: string
  time_window: string
  system_health: CommandSystemHealthDTO
  kpis: CommandKpisDTO
  reliability_trend: CommandReliabilityTrendPointDTO[]
  latency_percentiles: CommandLatencyPercentilesDTO
  outcomes: CommandOutcomesBreakdownDTO
  knowledge_health: CommandKnowledgeHealthDTO
  alerts: ExecutiveDashboardAlertDTO[]
}

export interface QueryExecutionLedgerItemDTO {
  id: string
  correlation_id: string
  query_text: string
  outcome: string
  confidence_score: number | null
  reliability_score: number | null
  hallucination_score: number | null
  retry_attempts: number
  duration_ms: number
  is_safe_to_serve: boolean
  timestamp: string
  has_retrieval_trace: boolean
}

export interface QueryExecutionLedgerDTO {
  items: QueryExecutionLedgerItemDTO[]
  total: number
  limit: number
  offset: number
  time_window: string
}

export interface RetrievalTraceDetailDTO {
  dense_candidate_count: number
  sparse_candidate_count: number
  merged_unique_count: number
  final_top_k: number
  retrieval_duration_ms: number
  stage_breakdown: Record<string, any>
}

export interface QueryExecutionTraceDTO {
  id: string
  correlation_id: string
  tenant_id: string
  query_text: string
  outcome: string
  confidence_score: number | null
  reliability_score: number | null
  hallucination_score: number | null
  retry_attempts: number
  total_duration_ms: number
  is_safe_to_serve: boolean
  timestamp: string
  retrieval: RetrievalTraceDetailDTO | null
  diagnostics: Record<string, any>
}

