import { create } from 'zustand'
import { knowledgeHealthService } from '@/services/knowledgeHealthService'
import type {
  HealthScanJobDTO,
  MigrationJobDTO,
  ParityAuditDTO,
  PurgeSummaryDTO,
  ScanType,
} from '@/types'

interface KnowledgeHealthState {
  scanHistory: HealthScanJobDTO[]
  totalJobs: number
  parityAudit: ParityAuditDTO | null
  activeJob: HealthScanJobDTO | null
  activeMigration: MigrationJobDTO | null
  isLoading: boolean
  isScanning: boolean
  error: string | null
}

interface KnowledgeHealthActions {
  fetchParity: () => Promise<ParityAuditDTO | null>
  runScan: (scanType: ScanType) => Promise<HealthScanJobDTO | null>
  fetchScanHistory: (scanType?: string, page?: number, size?: number) => Promise<void>
  rotateModel: (provider: string, model: string) => Promise<MigrationJobDTO | null>
  purgeDocument: (documentId: string) => Promise<PurgeSummaryDTO | null>
  clearError: () => void
}

export const useKnowledgeHealthStore = create<KnowledgeHealthState & KnowledgeHealthActions>()(
  (set, get) => ({
    scanHistory: [],
    totalJobs: 0,
    parityAudit: null,
    activeJob: null,
    activeMigration: null,
    isLoading: false,
    isScanning: false,
    error: null,

    fetchParity: async () => {
      set({ isLoading: true, error: null })
      try {
        const audit = await knowledgeHealthService.checkParity()
        set({ parityAudit: audit, isLoading: false })
        return audit
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch parity audit'
        set({ error: message, isLoading: false })
        return null
      }
    },

    runScan: async (scanType: ScanType) => {
      set({ isScanning: true, error: null })
      try {
        const job = await knowledgeHealthService.triggerHealthScan(scanType)
        set((state) => ({
          activeJob: job,
          isScanning: false,
          scanHistory: [job, ...state.scanHistory],
          totalJobs: state.totalJobs + 1,
        }))
        // Automatically re-verify parity after scan completes
        await get().fetchParity()
        return job
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to initiate health scan'
        set({ error: message, isScanning: false })
        return null
      }
    },

    fetchScanHistory: async (scanType?: string, page = 1, size = 20) => {
      set({ isLoading: true, error: null })
      try {
        const result = await knowledgeHealthService.listHealthScans(scanType, page, size)
        set({
          scanHistory: result.items,
          totalJobs: result.total,
          isLoading: false,
        })
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch scan history'
        set({ error: message, isLoading: false })
      }
    },

    rotateModel: async (provider: string, model: string) => {
      set({ isLoading: true, error: null })
      try {
        const migration = await knowledgeHealthService.rotateModel(provider, model)
        set({ activeMigration: migration, isLoading: false })
        return migration
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to trigger model rotation'
        set({ error: message, isLoading: false })
        return null
      }
    },

    purgeDocument: async (documentId: string) => {
      set({ isLoading: true, error: null })
      try {
        const summary = await knowledgeHealthService.purgeDocument(documentId)
        set({ isLoading: false })
        await get().fetchParity()
        return summary
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to purge document'
        set({ error: message, isLoading: false })
        return null
      }
    },

    clearError: () => set({ error: null }),
  }),
)
