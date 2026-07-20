import { get, post } from '@/api/wrapper'
import type {
  EmbeddingJobDTO,
  EmbeddingMetricsDTO,
  EmbeddingProcessRequestDTO,
  PaginatedJobResponse,
  ProviderInfoDTO,
} from '@/types'

export const embeddingService = {
  async listProviders(): Promise<ProviderInfoDTO[]> {
    return get<ProviderInfoDTO[]>('/embeddings/providers')
  },

  async getMetrics(): Promise<EmbeddingMetricsDTO> {
    return get<EmbeddingMetricsDTO>('/embeddings/metrics')
  },

  async listJobs(
    documentId?: string,
    status?: string,
    page = 1,
    size = 20,
  ): Promise<PaginatedJobResponse> {
    const params: Record<string, unknown> = { page, size }
    if (documentId) params.document_id = documentId
    if (status && status !== 'ALL') params.status = status
    return get<PaginatedJobResponse>('/embeddings/jobs', params)
  },

  async getJobDetail(jobId: string): Promise<EmbeddingJobDTO> {
    return get<EmbeddingJobDTO>(`/embeddings/jobs/${jobId}`)
  },

  async createJob(payload: EmbeddingProcessRequestDTO): Promise<EmbeddingJobDTO> {
    return post<EmbeddingJobDTO>('/embeddings/jobs', payload)
  },
}
