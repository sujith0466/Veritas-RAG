import { del, get, post } from '@/api/wrapper'
import type {
  ChunkCreateRequest,
  ChunkDetailResponse,
  ChunkListResponse,
  ChunkMetricsDTO,
  StrategyInfoDTO,
} from '@/types'

export const chunkService = {
  async listStrategies(): Promise<StrategyInfoDTO[]> {
    return get<StrategyInfoDTO[]>('/chunks/strategies')
  },

  async getMetrics(documentId?: string): Promise<ChunkMetricsDTO> {
    const params: Record<string, unknown> = {}
    if (documentId) params.document_id = documentId
    return get<ChunkMetricsDTO>('/chunks/metrics', params)
  },

  async processDocument(
    documentId: string,
    payload: ChunkCreateRequest = {},
    asyncMode = true,
    versionId?: string,
  ): Promise<{ status: string; task_id?: string; chunk_count?: number; duration_ms?: number }> {
    const params: Record<string, unknown> = { async_mode: asyncMode }
    if (versionId) params.version_id = versionId
    return post(`/chunks/process/${documentId}?async_mode=${asyncMode}${versionId ? `&version_id=${versionId}` : ''}`, payload)
  },

  async listDocumentChunks(
    documentId: string,
    page = 1,
    size = 50,
    strategy?: string,
    versionId?: string,
  ): Promise<ChunkListResponse> {
    const params: Record<string, unknown> = { page, size }
    if (strategy && strategy !== 'ALL') params.strategy = strategy
    if (versionId) params.version_id = versionId
    return get<ChunkListResponse>(`/chunks/document/${documentId}`, params)
  },

  async getChunkDetail(chunkId: string): Promise<ChunkDetailResponse> {
    return get<ChunkDetailResponse>(`/chunks/${chunkId}`)
  },

  async deleteDocumentChunks(documentId: string, versionId?: string): Promise<{ deleted_count: number }> {
    const params: Record<string, unknown> = {}
    if (versionId) params.version_id = versionId
    return del<{ deleted_count: number }>(`/chunks/document/${documentId}${versionId ? `?version_id=${versionId}` : ''}`)
  },
}
