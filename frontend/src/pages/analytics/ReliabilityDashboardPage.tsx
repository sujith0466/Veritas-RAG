import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, FileText } from 'lucide-react'
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
} from '@/types'
import { ReliabilityScoreCard } from './components/ReliabilityScoreCard'
import { ConfidenceTrendsChart } from './components/ConfidenceTrendsChart'
import { ReliabilityTrendsChart } from './components/ReliabilityTrendsChart'
import { RetryAnalysisCard } from './components/RetryAnalysisCard'
import { RetrievalQualityCard } from './components/RetrievalQualityCard'
import { LiveQueryMonitorTable } from './components/LiveQueryMonitorTable'

export function ReliabilityDashboardPage() {
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
  const latestScore = relHistory && relHistory.scores.length > 0
    ? relHistory.scores[relHistory.scores.length - 1]
    : successRate ? successRate.success_rate_percentage : 95.0

  const latestMovingAvg = relHistory && relHistory.moving_average_scores.length > 0
    ? relHistory.moving_average_scores[relHistory.moving_average_scores.length - 1]
    : latestScore

  return (
    <PageTransition>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <PageHeader
          title="AI Reliability & Verification Intelligence"
          description="Real-time observability into pre-generation confidence, self-correction interventions, and retrieval precision."
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

      {/* Top Banner / Executive Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        <div className="lg:col-span-12">
          <ReliabilityScoreCard
            score={latestScore}
            movingAverage={latestMovingAvg}
            successRate={successRate}
            latency={latency}
            isLoading={isLoading}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        <div className="lg:col-span-12">
          <ReliabilityTrendsChart
            trends={relTrends}
            isLoading={isLoading}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        <div className="lg:col-span-7">
          <ConfidenceTrendsChart
            trends={trends}
            distribution={confidence}
            isLoading={isLoading}
          />
        </div>
        <div className="lg:col-span-5 flex flex-col gap-6">
          <RetryAnalysisCard
            successRate={successRate}
            isLoading={isLoading}
          />
          <RetrievalQualityCard
            searchAnalytics={searchAnalytics}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Bottom Grid: Live Query Execution Audit Monitor */}
      <div className="grid grid-cols-1 gap-6">
        <LiveQueryMonitorTable
          items={historyItems}
          total={historyTotal}
          page={page}
          pageSize={20}
          isLoading={isLoading}
          onPageChange={(newPage) => setPage(newPage)}
          onOutcomeFilterChange={(outcome) => {
            setOutcomeFilter(outcome)
            setPage(1)
          }}
          selectedOutcome={outcomeFilter}
        />
      </div>

      <ReportExportDialog isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
    </PageTransition>
  )
}
