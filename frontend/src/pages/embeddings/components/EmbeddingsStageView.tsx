import * as React from 'react'
import { Cpu, RefreshCw, AlertCircle } from 'lucide-react'
import { Button } from '@/components/common'
import { embeddingService } from '@/services/embeddingService'
import { documentService } from '@/services/documentService'
import type {
  DocumentResponse,
  EmbeddingJobDTO,
  EmbeddingMetricsDTO,
  EmbeddingProcessRequestDTO,
  ProviderInfoDTO,
} from '@/types'
import { ProviderConfigCard, TokenUsageChart, EmbeddingJobTable } from './index'

/**
 * Valid document statuses eligible for embedding or re-embedding.
 * Matches ChunksStageView document eligibility: documents must have extracted or ready content.
 */
const ELIGIBLE_DOCUMENT_STATUSES = new Set([
  'READY',
  'PROCESSED',
  'CHUNKED',
  'EMBEDDING',
  'EMBEDDED',
  'VECTOR_SYNC',
])

export function EmbeddingsStageView() {
  const [providers, setProviders] = React.useState<ProviderInfoDTO[]>([])
  const [metrics, setMetrics] = React.useState<EmbeddingMetricsDTO | null>(null)
  const [documents, setDocuments] = React.useState<DocumentResponse[]>([])
  const [jobs, setJobs] = React.useState<EmbeddingJobDTO[]>([])
  const [totalJobs, setTotalJobs] = React.useState<number>(0)
  const [page, setPage] = React.useState<number>(1)
  const [statusFilter, setStatusFilter] = React.useState<string>('ALL')

  const [isLoadingInitial, setIsLoadingInitial] = React.useState<boolean>(true)
  const [isLoadingJobs, setIsLoadingJobs] = React.useState<boolean>(false)
  const [isCreating, setIsCreating] = React.useState<boolean>(false)
  const [stageError, setStageError] = React.useState<string | null>(null)

  const fetchInitialData = React.useCallback(async () => {
    setIsLoadingInitial(true)
    setStageError(null)
    try {
      const [provList, metricsSummary, docList, jobList] = await Promise.all([
        embeddingService.listProviders(),
        embeddingService.getMetrics().catch((err) => {
          console.warn('Failed to load metrics, fallback to null:', err)
          return null
        }),
        // Fetch without status filter so backend returns all active documents,
        // allowing client-side inclusion of READY and PROCESSED/CHUNKED documents.
        documentService.listDocuments(1, 100).catch((err) => {
          console.warn('Failed to load documents, fallback to empty:', err)
          return { items: [], total: 0, page: 1, page_size: 100, pages: 1 }
        }),
        embeddingService.listJobs(undefined, statusFilter, page, 20),
      ])
      setProviders(provList || [])
      setMetrics(metricsSummary)

      const rawDocs = docList?.items || []
      const eligibleDocs = rawDocs.filter((d) =>
        ELIGIBLE_DOCUMENT_STATUSES.has(d.status?.toUpperCase() || '')
      )
      setDocuments(eligibleDocs)
      setJobs(jobList?.items || [])
      setTotalJobs(jobList?.total || 0)
    } catch (err: any) {
      console.error('Failed to load embedding subsystem data:', err)
      setStageError(err?.message || 'Unable to load embedding workspace data.')
    } finally {
      setIsLoadingInitial(false)
    }
  }, [page, statusFilter])

  const fetchJobs = React.useCallback(async (pageNum: number, status: string) => {
    setIsLoadingJobs(true)
    try {
      const resp = await embeddingService.listJobs(undefined, status, pageNum, 20)
      setJobs(resp.items || [])
      setTotalJobs(resp.total || 0)
    } catch (err: any) {
      console.error('Failed to fetch embedding jobs:', err)
    } finally {
      setIsLoadingJobs(false)
    }
  }, [])

  const refreshMetricsAndJobs = React.useCallback(async () => {
    try {
      const [metricsSummary, jobList] = await Promise.all([
        embeddingService.getMetrics().catch(() => null),
        embeddingService.listJobs(undefined, statusFilter, page, 20),
      ])
      if (metricsSummary) setMetrics(metricsSummary)
      setJobs(jobList?.items || [])
      setTotalJobs(jobList?.total || 0)
    } catch (err: any) {
      console.error('Failed to refresh embedding metrics and jobs:', err)
    }
  }, [page, statusFilter])

  // Initial load
  React.useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  // Polling loop when jobs are active (PENDING or PROCESSING)
  React.useEffect(() => {
    const hasActiveJobs = jobs.some(
      (j) => j.status === 'PENDING' || j.status === 'PROCESSING'
    )
    if (!hasActiveJobs) return

    const interval = setInterval(() => {
      refreshMetricsAndJobs()
    }, 3000)

    return () => clearInterval(interval)
  }, [jobs, refreshMetricsAndJobs])

  const handlePageChange = (newPage: number) => {
    setPage(newPage)
    fetchJobs(newPage, statusFilter)
  }

  const handleStatusChange = (newStatus: string) => {
    setStatusFilter(newStatus)
    setPage(1)
    fetchJobs(1, newStatus)
  }

  const handleCreateJob = async (payload: EmbeddingProcessRequestDTO) => {
    setIsCreating(true)
    setStageError(null)
    try {
      await embeddingService.createJob(payload)
      await refreshMetricsAndJobs()
    } catch (err: any) {
      console.error('Failed to initiate embedding job:', err)
      setStageError(err?.message || 'Failed to initiate embedding job. Please verify provider status.')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Stage Action Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-2 border-b border-border/60">
        <div>
          <h2 className="text-base font-bold text-foreground">
            Stage 2: Vector Embeddings & Token Budget
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manage semantic embedding models, monitor token budget consumption, and orchestrate batch chunk vector encoding.
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={refreshMetricsAndJobs}
          disabled={isLoadingJobs}
          className="gap-2 shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoadingJobs ? 'animate-spin' : ''}`} />
          Refresh Stage
        </Button>
      </div>

      {/* Stage-Level Error Alert (Isolated) */}
      {stageError && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 flex items-center justify-between text-xs text-destructive">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{stageError}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchInitialData}
            className="text-xs border-destructive/30 hover:bg-destructive/20 text-destructive h-7 px-2.5"
          >
            Retry
          </Button>
        </div>
      )}

      {/* Provider Catalog Cards */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Cpu className="w-4 h-4 text-primary" />
            Registered Vector Engines
          </h3>
          <span className="text-xs text-muted-foreground font-medium">
            {providers.filter((p) => p.is_available).length} of {providers.length} engines online
          </span>
        </div>

        {isLoadingInitial && providers.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="h-56 bg-surface rounded-xl border border-border animate-pulse" />
            <div className="h-56 bg-surface rounded-xl border border-border animate-pulse" />
            <div className="h-56 bg-surface rounded-xl border border-border animate-pulse" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {providers.map((provider) => (
              <ProviderConfigCard key={provider.provider} provider={provider} />
            ))}
          </div>
        )}
      </section>

      {/* Token Budget Utilization & KPIs */}
      <section className="space-y-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Token Budget & Pipeline Telemetry
        </h3>
        <TokenUsageChart metrics={metrics} isLoading={isLoadingInitial} />
      </section>

      {/* Batch Jobs Orchestration Table */}
      <section>
        <EmbeddingJobTable
          jobs={jobs}
          isLoading={isLoadingJobs || isLoadingInitial}
          totalJobs={totalJobs}
          page={page}
          onPageChange={handlePageChange}
          statusFilter={statusFilter}
          onStatusFilterChange={handleStatusChange}
          onRefresh={() => fetchJobs(page, statusFilter)}
          documents={documents}
          providers={providers}
          onCreateJob={handleCreateJob}
          isCreating={isCreating}
        />
      </section>
    </div>
  )
}
