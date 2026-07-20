/**
 * Document Intelligence frontend domain models (`ADR-005`).
 */

export interface StageMetricDTO {
  stage: string
  duration_ms: number
  status: string
}

export interface DocumentManifestDTO {
  manifest_version: string
  document_id: string
  version_id: string
  version_number: number
  tenant_id: string
  owner_user_id?: string | null
  filename: string
  original_filename: string
  mime_type: string
  file_size_bytes: number
  checksum_sha256: string
  storage_provider: string
  original_storage_key: string
  normalized_text_path?: string | null
  metadata_json_path?: string | null
  page_count: number
  word_count: number
  language?: string
  encoding?: string | null
  stage_metrics: StageMetricDTO[]
  extraction_metadata: Record<string, unknown>
  created_at: string
}

export interface DocumentVersionDTO {
  id: string
  document_id: string
  version_number: number
  storage_object_id: string
  content_hash: string
  extracted_text_path?: string
  metadata_json?: Record<string, unknown>
  created_at: string
}

export interface DocumentResponse {
  id: string
  tenant_id: string
  filename: string
  original_filename: string
  status: string
  latest_version_id?: string
  word_count: number
  page_count: number
  language?: string
  created_at: string
  updated_at: string
}

export interface DocumentDetailResponse extends DocumentResponse {
  versions: DocumentVersionDTO[]
  manifest?: DocumentManifestDTO
}

export interface ProcessingStatusResponse {
  document_id: string
  status: string
  current_step: string
  progress_percent: number
  retry_count: number
  error_code?: string
  error_message?: string
  updated_at: string
}

export interface UploadResponse {
  document_id: string
  version_id: string
  job_id: string
  status: string
  filename: string
  original_filename: string
  file_size_bytes: number
  created_at: string
}

export interface DocumentListResponse {
  items: DocumentResponse[]
  total: number
  page: number
  page_size: number
  pages: number
}
