import { useState, useMemo } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { analyticsService } from '@/services/analyticsService'
import { useWorkspaceStore } from '@/stores/workspaceStore'

import {
  WorkspaceAnalyticsHeader,
  ExecutiveKpiGrid,
  WorkspaceActivityChart,
  PopularTopicsCard,
  UnansweredQueriesCard,
  MostCitedDocumentsCard,
  StalenessReportCard,
  type AnalyticsTimeRange,
} from '@/components/analytics'

export function WorkspaceAnalyticsPage() {
  const shouldReduceMotion = useReducedMotion()
  const queryClient = useQueryClient()
  const currentWorkspace = useWorkspaceStore((s) => s.currentWorkspace)

  const [timeRange, setTimeRange] = useState<AnalyticsTimeRange>('30d')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(new Date())

  // Compute start_time & end_time ISO strings based on timeRange
  const { startTime, endTime } = useMemo(() => {
    const now = new Date()
    let start: Date | null = null

    switch (timeRange) {
      case '24h':
        start = new Date(now.getTime() - 24 * 60 * 60 * 1000)
        break
      case '7d':
        start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        break
      case '30d':
        start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        break
      case '90d':
        start = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000)
        break
      case 'all':
      default:
        start = null
        break
    }

    return {
      startTime: start ? start.toISOString() : undefined,
      endTime: start ? now.toISOString() : undefined,
    }
  }, [timeRange])

  // Overview telemetry (Active users, documents, queries)
  const {
    data: overviewData,
    isLoading: isOverviewLoading,
    isError: isOverviewError,
    refetch: refetchOverview,
    isFetching: isOverviewFetching,
  } = useQuery({
    queryKey: ['workspace-overview', startTime, endTime],
    queryFn: () => analyticsService.getWorkspaceOverview(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  // Grounded Success & Failure rate metrics
  const {
    data: successRateData,
    isLoading: isSuccessRateLoading,
    isError: isSuccessRateError,
    refetch: refetchSuccessRate,
    isFetching: isSuccessRateFetching,
  } = useQuery({
    queryKey: ['workspace-success-rate', startTime, endTime],
    queryFn: () => analyticsService.getSuccessRate(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  // Reliability trends history
  const {
    data: trendsData,
    isLoading: isTrendsLoading,
    isError: isTrendsError,
    refetch: refetchTrends,
    isFetching: isTrendsFetching,
  } = useQuery({
    queryKey: ['workspace-reliability-trends', startTime, endTime],
    queryFn: () => analyticsService.getReliabilityTrends(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  // Server latency percentiles
  const {
    data: latencyData,
    isLoading: isLatencyLoading,
    isError: isLatencyError,
    refetch: refetchLatency,
    isFetching: isLatencyFetching,
  } = useQuery({
    queryKey: ['workspace-latency', startTime, endTime],
    queryFn: () => analyticsService.getLatencyAnalytics(startTime, endTime),
    staleTime: 5 * 60 * 1000,
  })

  // Coordinated manual refresh
  const isRefreshing =
    isOverviewFetching || isSuccessRateFetching || isTrendsFetching || isLatencyFetching

  const handleRefresh = async () => {
    setLastUpdated(new Date())
    await Promise.all([
      refetchOverview(),
      refetchSuccessRate(),
      refetchTrends(),
      refetchLatency(),
      queryClient.invalidateQueries({ queryKey: ['popular-topics'] }),
      queryClient.invalidateQueries({ queryKey: ['unanswered-queries'] }),
      queryClient.invalidateQueries({ queryKey: ['most-cited-documents'] }),
      queryClient.invalidateQueries({ queryKey: ['staleness-report'] }),
    ])
  }

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35 }}
      className="container max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6 sm:space-y-8"
    >
      {/* 1. Header with Context, Time Range Controls, and Refresh */}
      <WorkspaceAnalyticsHeader
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
        lastUpdated={lastUpdated}
        workspaceName={currentWorkspace?.name || 'Primary Workspace'}
        workspaceStatus={currentWorkspace?.status || 'ACTIVE'}
      />

      {/* 2. Executive KPI Summary Grid (Active Users, Docs, Queries, Grounded Reliability) */}
      <ExecutiveKpiGrid
        overview={overviewData}
        successRate={successRateData}
        isLoading={isOverviewLoading || isSuccessRateLoading}
        isError={isOverviewError || isSuccessRateError}
        onRetry={() => {
          refetchOverview()
          refetchSuccessRate()
        }}
      />

      {/* 3. Activity & Grounding Reliability Telemetry */}
      <WorkspaceActivityChart
        trends={trendsData}
        latency={latencyData}
        isLoading={isTrendsLoading || isLatencyLoading}
        isError={isTrendsError || isLatencyError}
        onRetry={() => {
          refetchTrends()
          refetchLatency()
        }}
      />

      {/* 4. Topic Intelligence & Unanswered Query Forensics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PopularTopicsCard startTime={startTime} endTime={endTime} />
        <UnansweredQueriesCard startTime={startTime} endTime={endTime} />
      </div>

      {/* 5. Most Cited Knowledge Assets & Document Staleness Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MostCitedDocumentsCard startTime={startTime} endTime={endTime} />
        <StalenessReportCard />
      </div>
    </motion.div>
  )
}
export default WorkspaceAnalyticsPage
