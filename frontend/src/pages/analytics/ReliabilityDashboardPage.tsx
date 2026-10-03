import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
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
  ConfidenceAnalyticsDTO,
  LatencyAnalyticsDTO,
  QueryHistoryItemDTO,
  QueryTrendsDTO,
  ReliabilityHistoryDTO,
  ReliabilityTrendDTO,
  SearchAnalyticsDTO,
  SuccessRateDTO,
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
  const [isLoading, setIsLoading] = useState(true)
  const [isExportOpen, setIsExportOpen] = useState(false)

  // Analytical state
  const [successRate, setSuccessRate] = useState<SuccessRateDTO | null>(null)
  const [latency, setLatency] = useState<LatencyAnalyticsDTO | null>(null)
  const [confidence, setConfidence] = useState<ConfidenceAnalyticsDTO | null>(null)
  const [trends, setTrends] = useState<QueryTrendsDTO | null>(null)
  const [relHistory, setRelHistory] = useState<ReliabilityHistoryDTO | null>(null)
  const [relTrends, setRelTrends] = useState<ReliabilityTrendDTO[] | null>(null)
  const [searchAnalytics, setSearchAnalytics] = useState<SearchAnalyticsDTO | null>(null)
  const [historyItems, setHistoryItems] = useState<QueryHistoryItemDTO[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)

  const fetchAllData = useCallback(async () => {
    setIsLoading(true)
    try {
      const [
        srData,
        latData,
        confData,
        trendsData,
        relData,
        relTrendsData,
        searchData,
        historyData,
      ] = await Promise.all([
        analyticsService.getSuccessRate(),
        analyticsService.getLatencyAnalytics(),
        analyticsService.getConfidenceAnalytics(),
        analyticsService.getQueryTrends(timeInterval),
        analyticsService.getReliabilityHistory(timeInterval),
        analyticsService.getReliabilityTrends(),
        analyticsService.getSearchAnalytics(),
        analyticsService.getQueryHistory(page, 20, outcomeFilter),
      ])

      setSuccessRate(srData)
      setLatency(latData)
      setConfidence(confData)
      setTrends(trendsData)
      setRelHistory(relData)
      setRelTrends(relTrendsData)
      setSearchAnalytics(searchData)
      setHistoryItems(historyData.items)
      setHistoryTotal(historyData.total)
    } catch (err) {
      console.error('Failed to load reliability analytics:', err)
    } finally {
      setIsLoading(false)
    }
  }, [timeInterval, page, outcomeFilter])

  useEffect(() => {
    fetchAllData()
  }, [fetchAllData])

  useEffect(() => {
    if (!autoRefresh) return
    const timer = setInterval(() => {
      fetchAllData()
    }, 15000)
    return () => clearInterval(timer)
  }, [autoRefresh, fetchAllData])

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
            onClick={fetchAllData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
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
