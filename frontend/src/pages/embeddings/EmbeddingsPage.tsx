import * as React from 'react'
import { Cpu, RefreshCw } from 'lucide-react'
import { Button, PageHeader } from '@/components/common'
import { PageTransition } from '@/components/layouts'
import { embeddingService } from '@/services/embeddingService'
import { documentService } from '@/services/documentService'
import type {
  DocumentResponse,
  EmbeddingJobDTO,
  EmbeddingMetricsDTO,
  EmbeddingProcessRequestDTO,
  ProviderInfoDTO,
} from '@/types'
import { ProviderConfigCard, TokenUsageChart, EmbeddingJobTable } from './components'

export function EmbeddingsPage() {
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

  const fetchInitialData = React.useCallback(async () => {
    try {
      const [provList, metricsSummary, docList, jobList] = await Promise.all([
        embeddingService.listProviders(),
        embeddingService.getMetrics(),
        documentService.listDocuments(1, 100, 'PROCESSED'),
        embeddingService.listJobs(undefined, statusFilter, page, 20),
      ])
      setProviders(provList || [])
      setMetrics(metricsSummary)
      setDocuments(docList.items || [])
      setJobs(jobList.items || [])
      setTotalJobs(jobList.total || 0)
    } catch (err) {
      console.error('Failed to load embedding subsystem initial data:', err)
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
    } catch (err) {
      console.error('Failed to fetch embedding jobs:', err)
    } finally {
      setIsLoadingJobs(false)
    }
  }, [])

  const refreshMetricsAndJobs = React.useCallback(async () => {
    try {
      const [metricsSummary, jobList] = await Promise.all([
        embeddingService.getMetrics(),
        embeddingService.listJobs(undefined, statusFilter, page, 20),
      ])
      setMetrics(metricsSummary)
      setJobs(jobList.items || [])
      setTotalJobs(jobList.total || 0)
    } catch (err) {
      console.error('Failed to refresh metrics and jobs:', err)
    }
  }, [page, statusFilter])

  // Initial load
  React.useEffect(() => {
    fetchInitialData()
  }, [fetchInitialData])

  // Polling loop when jobs are active
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
    try {
      await embeddingService.createJob(payload)
      await refreshMetricsAndJobs()
    } catch (err) {
      console.error('Failed to initiate embedding job:', err)
    } finally {
      setIsCreating(false)
    }
  }

  if (isLoadingInitial) {
    return (
      <PageTransition className="p-8 space-y-6">
        <div className="h-10 bg-muted rounded-xl w-64 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="h-64 bg-surface rounded-xl border border-border animate-pulse" />
          <div className="h-64 bg-surface rounded-xl border border-border animate-pulse" />
          <div className="h-64 bg-surface rounded-xl border border-border animate-pulse" />
        </div>
        <div className="h-96 bg-surface rounded-xl border border-border animate-pulse" />
      </PageTransition>
    )
  }

  return (
    <PageTransition className="p-8 space-y-8 max-w-7xl mx-auto pb-12">
      <PageHeader
        title="Knowledge Vectorization (Embeddings)"
        description="Manage semantic embedding models, monitor token budget consumption, and orchestrate batch chunk vector encoding."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={refreshMetricsAndJobs}
            className="flex items-center gap-1.5 text-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Subsystem</span>
          </Button>
        }
      />

      {/* Provider Catalog Cards */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
            <Cpu className="w-4 h-4 text-primary" />
            Registered Vector Engines
          </h2>
          <span className="text-xs text-muted-foreground font-medium">
            {providers.filter((p) => p.is_available).length} of {providers.length} engines online
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {providers.map((provider) => (
            <ProviderConfigCard key={provider.provider} provider={provider} />
          ))}
        </div>
      </section>

      {/* Token Budget Utilization & KPIs */}
      <section className="space-y-4 pt-4">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
          Token Budget & Pipeline Telemetry
        </h2>
        <TokenUsageChart metrics={metrics} isLoading={false} />
      </section>

      {/* Batch Jobs Orchestration Table */}
      <section className="pt-4">
        <EmbeddingJobTable
          jobs={jobs}
          isLoading={isLoadingJobs}
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
    </PageTransition>
  )
}
