export interface ProviderModelInfoDTO {
  model_name: string
  dimension: number
  max_input_tokens: number
  is_default: boolean
}

export interface ProviderInfoDTO {
  provider: string
  display_name: string
  description: string
  is_available: boolean
  models: ProviderModelInfoDTO[]
}

export interface EmbeddingJobDTO {
  job_id: string
  tenant_id: string
  document_id: string
  document_version_id: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | string
  provider: string
  model_name: string
  total_chunks: number
  processed_chunks: number
  failed_chunks: number
  total_tokens_consumed: number
  error_message?: string | null
  created_at: string
  updated_at: string
  progress_percentage: number
}

export interface EmbeddingMetricsDTO {
  tenant_id: string
  monthly_token_quota: number
  total_tokens_consumed: number
  remaining_tokens: number
  total_vectors_stored: number
  active_jobs_count: number
  completed_jobs_count: number
  failed_jobs_count: number
  provider_distribution: Record<string, number>
}

export interface EmbeddingProcessRequestDTO {
  document_id: string
  document_version_id: string
  provider?: string | null
  model_name?: string | null
  batch_size?: number
  force_reembed?: boolean
}

export interface PaginatedJobResponse {
  items: EmbeddingJobDTO[]
  total: number
  page: number
  size: number
  pages: number
}
