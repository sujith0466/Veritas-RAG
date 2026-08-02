export type ScanType = 'ORPHAN_SWEEP' | 'PARITY_AUDIT' | 'MODEL_ROTATION_SCAN' | 'ALL'
export type ScanStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED'

export interface HealthScanRequestDTO {
  scan_type: ScanType
}

export interface HealthScanJobDTO {
  id: string
  tenant_id: string
  scan_type: ScanType | string
  status: ScanStatus | string
  orphans_found: number
  orphans_purged: number
  stale_chunks_found: number
  parity_status: string
  duration_ms: number
  error_message?: string | null
  created_at: string
  updated_at: string
}

export interface ParityAuditDTO {
  tenant_id: string
  pg_chunk_count: number
  qdrant_point_count: number
  is_synced: boolean
  parity_status: string
  checked_at: string
}

export interface ModelRotationRequestDTO {
  new_provider: string
  new_model: string
}

export interface MigrationJobDTO {
  job_id: string
  tenant_id: string
  target_provider: string
  target_model: string
  stale_chunks_enqueued: number
  status: string
  started_at: string
}
