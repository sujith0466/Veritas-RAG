export interface StrategyInfoDTO {
  name: string
  display_name: string
  description: string
  supported_mime_types: string[]
  default_max_characters: number
  default_overlap_characters: number
  is_placeholder: boolean
}

export interface ChunkRelationshipDTO {
  source_chunk_id: string
  target_chunk_id: string
  relationship_type: string
  metadata_json?: Record<string, unknown>
}

export interface ChunkResponse {
  id: string
  tenant_id: string
  document_id: string
  document_version_id: string
  chunk_index: number
  content: string
  content_hash: string
  strategy_used: string
  token_count: number
  character_count: number
  previous_chunk_id?: string | null
  next_chunk_id?: string | null
  parent_chunk_id?: string | null
  page_numbers?: number[] | null
  section_path?: string[] | null
  is_embedded: boolean
  created_at: string
}

export interface ChunkDetailResponse extends ChunkResponse {
  metadata_json?: Record<string, unknown> | null
  relationships?: ChunkRelationshipDTO[]
}

export interface ChunkListResponse {
  items: ChunkResponse[]
  total: number
  page: number
  size: number
  document_id: string
  document_version_id: string
  strategy_used?: string | null
}

export interface ChunkMetricsDTO {
  total_chunks: number
  total_characters: number
  total_tokens: number
  average_chunk_characters: number
  average_chunk_tokens: number
  strategy_breakdown: Record<string, number>
  is_embedded_count: number
}

export interface ChunkCreateRequest {
  strategy?: string | null
  max_characters?: number
  overlap_characters?: number
}
