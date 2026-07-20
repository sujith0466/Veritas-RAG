/**
 * Hybrid Retrieval Engine UI Types (`ADR-002`, `ADR-005`).
 *
 * Defines TypeScript structures matching backend DTO contracts for
 * multi-stage hybrid retrieval comparisons (`POST /api/v1/retrieval/sandbox`).
 */

export interface CandidatePointDTO {
  chunk_id: string
  document_id: string
  document_version_id: string
  tenant_id: string
  content: string
  score: number
  source: 'dense' | 'sparse' | 'rrf'
  rank: number
  metadata?: Record<string, unknown>
}

export interface RankedEvidenceDTO {
  chunk_id: string
  document_id: string
  document_version_id: string
  tenant_id: string
  content: string
  rrf_score: number
  rerank_score: number
  final_rank: number
  metadata?: Record<string, unknown>
}

export interface RetrievalStageBreakdownDTO {
  dense_ms: number
  sparse_ms: number
  rrf_fusion_ms: number
  rerank_ms: number
  total_ms: number
}

export interface SearchSandboxResponseDTO {
  query_text: string
  tenant_id: string
  correlation_id: string
  dense_results: CandidatePointDTO[]
  sparse_results: CandidatePointDTO[]
  rrf_merged_results: CandidatePointDTO[]
  final_reranked_results: RankedEvidenceDTO[]
  stage_latencies: RetrievalStageBreakdownDTO
}

export interface SearchSandboxRequest {
  query: string
  top_k: number
  rrf_k: number
  dedup_threshold: number
  limit_dense: number
  limit_sparse: number
}
