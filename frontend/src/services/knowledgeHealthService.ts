import { del, get, post } from '@/api/wrapper'
import type {
  HealthScanJobDTO,
  HealthScanRequestDTO,
  MigrationJobDTO,
  ModelRotationRequestDTO,
  ParityAuditDTO,
  PurgeSummaryDTO,
  ScanType,
} from '@/types'

export interface PaginatedScanHistory {
  items: HealthScanJobDTO[]
  total: number
  page: number
  size: number
}

export const knowledgeHealthService = {
  async triggerHealthScan(scanType: ScanType): Promise<HealthScanJobDTO> {
    const payload: HealthScanRequestDTO = { scan_type: scanType }
    return post<HealthScanJobDTO>('/knowledge-health/scans', payload)
  },

  async listHealthScans(
    scanType?: string,
    page = 1,
    size = 20,
  ): Promise<PaginatedScanHistory> {
    const params: Record<string, unknown> = { page, size }
    if (scanType) {
      params.scan_type = scanType
    }
    return get<PaginatedScanHistory>('/knowledge-health/scans', params)
  },

  async checkParity(): Promise<ParityAuditDTO> {
    return get<ParityAuditDTO>('/knowledge-health/parity')
  },

  async rotateModel(newProvider: string, newModel: string): Promise<MigrationJobDTO> {
    const payload: ModelRotationRequestDTO = {
      new_provider: newProvider,
      new_model: newModel,
    }
    return post<MigrationJobDTO>('/knowledge-health/rotate-model', payload)
  },

  async purgeDocument(documentId: string): Promise<PurgeSummaryDTO> {
    return del<PurgeSummaryDTO>(`/knowledge-health/purge/${documentId}`)
  },

  async getStalenessReport(workspaceId: string): Promise<any> {
    return get<any>(`/knowledge-base/staleness/report`, { workspace_id: workspaceId })
  },

  async executeBulkRemediation(workspaceId: string, payload: any): Promise<any> {
    return post<any>(`/knowledge-base/staleness/remediate?workspace_id=${workspaceId}`, payload)
  },
}
