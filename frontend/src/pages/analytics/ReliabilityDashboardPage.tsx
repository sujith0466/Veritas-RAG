import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  RefreshCw,
  FileText,
  BarChart3,
  TrendingUp,
  Search,
  Terminal,
} from 'lucide-react'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { ReportExportDialog } from '@/components/analytics/ReportExportDialog'
import { analyticsService } from '@/services/analyticsService'
import type {
  QueryTraceDetailDTO,
  QuerySandboxResponseDTO,
} from '@/types'
import {
  OverviewTab,
  TrendsPerformanceTab,
  QueryExplorerTab,
  DiagnosticSandboxTab,
  ForensicTraceDrawer,
} from './components'

type TabType = 'overview' | 'trends' | 'explorer' | 'sandbox'

export function ReliabilityDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Read active tab from URL query params (default: 'overview')
  const currentTabParam = searchParams.get('tab')
  const activeTab: TabType =
    currentTabParam === 'trends' ||
    currentTabParam === 'explorer' ||
    currentTabParam === 'sandbox'
      ? currentTabParam
      : 'overview'

  const setActiveTab = (tab: TabType) => {
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    setSearchParams(next)
  }

  // Deep-linked trace inspection
  const deepLinkedTraceId = searchParams.get('traceId') || searchParams.get('query_id')
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(deepLinkedTraceId)
  const [selectedTraceData, setSelectedTraceData] = useState<QueryTraceDetailDTO | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(Boolean(deepLinkedTraceId))

  // Sync state if URL changes
  useEffect(() => {
    if (deepLinkedTraceId) {
      setSelectedTraceId(deepLinkedTraceId)
      setSelectedTraceData(null)
      setIsDrawerOpen(true)
    }
  }, [deepLinkedTraceId])

  const handleOpenTrace = (correlationId: string, initialData?: QueryTraceDetailDTO) => {
    setSelectedTraceId(correlationId)
    setSelectedTraceData(initialData || null)
    setIsDrawerOpen(true)
    const next = new URLSearchParams(searchParams)
    next.set('traceId', correlationId)
    setSearchParams(next)
  }

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false)
    setSelectedTraceId(null)
    setSelectedTraceData(null)
    const next = new URLSearchParams(searchParams)
    next.delete('traceId')
    next.delete('query_id')
    setSearchParams(next)
  }

  // Filters & Pagination
  const [timeInterval, setTimeInterval] = useState<'hourly' | 'daily' | 'weekly'>('daily')
  const [page, setPage] = useState(1)
  const [outcomeFilter, setOutcomeFilter] = useState<string | undefined>(undefined)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [isExportOpen, setIsExportOpen] = useState(false)

  const queryClient = useQueryClient()

  // 1. Core analytics metrics (cached with 60s stale time)
  const {
    data: coreData,
    isLoading: isCoreLoading,
    isFetching: isCoreFetching,
  } = useQuery({
    queryKey: ['reliability-core-metrics'],
    queryFn: async () => {
      const [sr, lat, conf, search] = await Promise.all([
        analyticsService.getSuccessRate(),
        analyticsService.getLatencyAnalytics(),
        analyticsService.getConfidenceAnalytics(),
        analyticsService.getSearchAnalytics(),
      ])
      return { sr, lat, conf, search }
    },
    staleTime: 60 * 1000,
    refetchInterval: autoRefresh ? 15000 : false,
  })

  // 2. Trends & historical scores (keyed by timeInterval, cached 60s)
  const {
    data: trendsGroup,
    isLoading: isTrendsLoading,
    isFetching: isTrendsFetching,
  } = useQuery({
    queryKey: ['reliability-trends', timeInterval],
    queryFn: async () => {
      const [trends, relHistory, relTrends] = await Promise.all([
        analyticsService.getQueryTrends(timeInterval),
        analyticsService.getReliabilityHistory(timeInterval),
        analyticsService.getReliabilityTrends(),
      ])
      return { trends, relHistory, relTrends }
    },
    staleTime: 60 * 1000,
    refetchInterval: autoRefresh ? 15000 : false,
  })

  // 3. Query history (keyed by page, outcomeFilter, cached 30s)
  const {
    data: historyData,
    isLoading: isHistoryLoading,
    isFetching: isHistoryFetching,
  } = useQuery({
    queryKey: ['reliability-history', page, outcomeFilter],
    queryFn: () => analyticsService.getQueryHistory(page, 20, outcomeFilter),
    staleTime: 30 * 1000,
    refetchInterval: autoRefresh ? 15000 : false,
  })

  const isLoading = isCoreLoading || isTrendsLoading || isHistoryLoading
  const isRefreshing = isCoreFetching || isTrendsFetching || isHistoryFetching

  const handleRefreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['reliability-core-metrics'] })
    queryClient.invalidateQueries({ queryKey: ['reliability-trends'] })
    queryClient.invalidateQueries({ queryKey: ['reliability-history'] })
  }

  const successRate = coreData?.sr ?? null
  const latency = coreData?.lat ?? null
  const confidence = coreData?.conf ?? null
  const searchAnalytics = coreData?.search ?? null

  const trends = trendsGroup?.trends ?? null
  const relHistory = trendsGroup?.relHistory ?? null
  const relTrends = trendsGroup?.relTrends ?? null

  const historyItems = historyData?.items ?? []
  const historyTotal = historyData?.total ?? 0

  // Derive latest reliability score & moving average
  const latestScore =
    relHistory && relHistory.scores.length > 0
      ? relHistory.scores[relHistory.scores.length - 1]
      : successRate
      ? successRate.success_rate_percentage
      : 95.0

  const latestMovingAvg =
    relHistory && relHistory.moving_average_scores.length > 0
      ? relHistory.moving_average_scores[relHistory.moving_average_scores.length - 1]
      : latestScore

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: BarChart3 },
    { id: 'trends' as const, label: 'Trends & Performance', icon: TrendingUp },
    { id: 'explorer' as const, label: 'Query Explorer', icon: Search },
    { id: 'sandbox' as const, label: 'Diagnostic Sandbox', icon: Terminal },
  ]

  return (
    <PageTransition>
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <PageHeader
          title="AI Reliability & Diagnostics Console"
          description="Authoritative observability into pre-generation confidence, verification telemetry, forensic traces, and pipeline diagnostics."
        />

        <div className="flex flex-wrap items-center gap-2">
          {/* Interval Selector */}
          <div className="flex items-center gap-1 bg-surface/80 p-1 rounded-lg border border-border/60 shadow-sm">
            {(['hourly', 'daily', 'weekly'] as const).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTimeInterval(t)
                  setPage(1)
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-colors ${
                  timeInterval === t
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Auto refresh button */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30'
                : 'bg-surface text-muted-foreground border-border/60 hover:text-foreground'
            }`}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Live Sync 15s' : 'Live Sync Off'}
          </button>

          {/* Manual Refresh */}
          <button
            onClick={handleRefreshAll}
            disabled={isLoading || isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {/* Export Report Button */}
          <button
            onClick={() => setIsExportOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary border border-primary/30 hover:bg-primary hover:text-primary-foreground transition-all shadow-sm"
          >
            <FileText className="h-3.5 w-3.5" />
            Export Audit Report
          </button>
        </div>
      </div>

      {/* Navigation Tabs Bar */}
      <div className="flex items-center border-b border-border/60 mb-6 gap-2">
        {tabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
                isActive
                  ? 'border-primary text-primary bg-primary/5'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border/60'
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && (
        <OverviewTab
          latestScore={latestScore}
          latestMovingAvg={latestMovingAvg}
          successRate={successRate}
          latency={latency}
          relTrends={relTrends}
          historyItems={historyItems}
          historyTotal={historyTotal}
          page={page}
          pageSize={20}
          isLoading={isLoading}
          outcomeFilter={outcomeFilter}
          selectedTraceId={selectedTraceId}
          onPageChange={(newPage) => setPage(newPage)}
          onOutcomeFilterChange={(outcome) => {
            setOutcomeFilter(outcome)
            setPage(1)
          }}
          onSelectTrace={(corrId) => handleOpenTrace(corrId)}
        />
      )}

      {activeTab === 'trends' && (
        <TrendsPerformanceTab
          relTrends={relTrends}
          trends={trends}
          confidence={confidence}
          successRate={successRate}
          searchAnalytics={searchAnalytics}
          isLoading={isLoading}
        />
      )}

      {activeTab === 'explorer' && (
        <QueryExplorerTab
          items={historyItems}
          total={historyTotal}
          page={page}
          pageSize={20}
          isLoading={isLoading}
          outcomeFilter={outcomeFilter}
          selectedTraceId={selectedTraceId}
          onPageChange={(newPage) => setPage(newPage)}
          onOutcomeFilterChange={(outcome) => {
            setOutcomeFilter(outcome)
            setPage(1)
          }}
          onSelectTrace={(corrId) => handleOpenTrace(corrId)}
        />
      )}

      {activeTab === 'sandbox' && (
        <DiagnosticSandboxTab
          onInspectTrace={(res: QuerySandboxResponseDTO) =>
            handleOpenTrace(res.correlation_id, res.trace_detail)
          }
        />
      )}

      {/* Forensic Trace Drawer (Accessible from any tab, deep-linkable) */}
      <ForensicTraceDrawer
        isOpen={isDrawerOpen}
        onClose={handleCloseDrawer}
        correlationId={selectedTraceId}
        initialTrace={selectedTraceData}
      />

      <ReportExportDialog isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
    </PageTransition>
  )
}
