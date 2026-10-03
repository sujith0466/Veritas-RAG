import { ReliabilityScoreCard } from './ReliabilityScoreCard'
import { ReliabilityTrendsChart } from './ReliabilityTrendsChart'
import { LiveQueryMonitorTable } from './LiveQueryMonitorTable'
import type {
  LatencyAnalyticsDTO,
  QueryHistoryItemDTO,
  ReliabilityTrendDTO,
  SuccessRateDTO,
} from '@/types'

interface OverviewTabProps {
  latestScore: number
  latestMovingAvg: number
  successRate: SuccessRateDTO | null
  latency: LatencyAnalyticsDTO | null
  relTrends: ReliabilityTrendDTO[] | null
  historyItems: QueryHistoryItemDTO[]
  historyTotal: number
  page: number
  pageSize: number
  isLoading: boolean
  outcomeFilter?: string
  selectedTraceId?: string | null
  onPageChange: (newPage: number) => void
  onOutcomeFilterChange: (outcome: string | undefined) => void
  onSelectTrace: (correlationId: string) => void
}

export function OverviewTab({
  latestScore,
  latestMovingAvg,
  successRate,
  latency,
  relTrends,
  historyItems,
  historyTotal,
  page,
  pageSize,
  isLoading,
  outcomeFilter,
  selectedTraceId,
  onPageChange,
  onOutcomeFilterChange,
  onSelectTrace,
}: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* Top Banner / Executive Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
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

      {/* Primary Trend Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-12">
          <ReliabilityTrendsChart
            trends={relTrends}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Live Query Execution Audit Monitor */}
      <div className="grid grid-cols-1 gap-6">
        <LiveQueryMonitorTable
          items={historyItems}
          total={historyTotal}
          page={page}
          pageSize={pageSize}
          isLoading={isLoading}
          onPageChange={onPageChange}
          onOutcomeFilterChange={onOutcomeFilterChange}
          selectedOutcome={outcomeFilter}
          onSelectTrace={onSelectTrace}
          selectedTraceId={selectedTraceId}
        />
      </div>
    </div>
  )
}
