export interface CollectionDetailDTO {
  collection_name: string
  total_points: number
  indexed_versions_count: number
}

export interface QdrantClusterHealthDTO {
  status: string
  active_collections_count: number
  total_points_stored: number
  collections: CollectionDetailDTO[]
}

export interface VectorIndexMetadataDTO {
  id: string
  tenant_id: string
  document_id: string
  document_version_id: string
  collection_name: string
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  points_count: number
  error_message?: string | null
}

export interface PurgeSummaryDTO {
  document_id: string
  tenant_id: string
  purged_points_count?: number
  qdrant_points_deleted?: number
  pg_chunks_deleted?: number
  is_fully_purged?: boolean
  duration_ms?: number
}

export interface VectorSyncRequestDTO {
  document_id: string
  collection_name?: string
}
