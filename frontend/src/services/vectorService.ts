import { del, get, post } from '@/api/wrapper'
import type {
  CollectionDetailDTO,
  PurgeSummaryDTO,
  QdrantClusterHealthDTO,
  VectorIndexMetadataDTO,
  VectorSyncRequestDTO,
} from '@/types'

export const vectorService = {
  async getHealth(): Promise<QdrantClusterHealthDTO> {
    return get<QdrantClusterHealthDTO>('/vectors/health')
  },

  async listCollections(): Promise<CollectionDetailDTO[]> {
    return get<CollectionDetailDTO[]>('/vectors/collections')
  },

  async getDocumentStatus(documentId: string): Promise<VectorIndexMetadataDTO[]> {
    return get<VectorIndexMetadataDTO[]>(`/vectors/document/${documentId}`)
  },

  async syncDocument(versionId: string, payload: VectorSyncRequestDTO): Promise<VectorIndexMetadataDTO> {
    return post<VectorIndexMetadataDTO>(`/vectors/sync/${versionId}`, payload)
  },

  async deleteDocumentPoints(documentId: string): Promise<PurgeSummaryDTO> {
    return del<PurgeSummaryDTO>(`/vectors/document/${documentId}`)
  },
}
