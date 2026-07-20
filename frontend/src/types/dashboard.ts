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
  total_queries_last_24h: number
  avg_reliability_score: number
  avg_confidence_score: number
  blocked_hallucinations_last_24h: number
  clarification_rate: number
  system_status: string
  recent_activity: ExecutiveDashboardActivityDTO[]
  security_alerts: ExecutiveDashboardAlertDTO[]
}
