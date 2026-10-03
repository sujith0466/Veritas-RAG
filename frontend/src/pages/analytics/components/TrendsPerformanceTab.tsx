import { ReliabilityTrendsChart } from './ReliabilityTrendsChart'
import { ConfidenceTrendsChart } from './ConfidenceTrendsChart'
import { RetryAnalysisCard } from './RetryAnalysisCard'
import { RetrievalQualityCard } from './RetrievalQualityCard'
import type {
  ConfidenceAnalyticsDTO,
  QueryTrendsDTO,
  ReliabilityTrendDTO,
  SearchAnalyticsDTO,
  SuccessRateDTO,
} from '@/types'

interface TrendsPerformanceTabProps {
  relTrends: ReliabilityTrendDTO[] | null
  trends: QueryTrendsDTO | null
  confidence: ConfidenceAnalyticsDTO | null
  successRate: SuccessRateDTO | null
  searchAnalytics: SearchAnalyticsDTO | null
  isLoading: boolean
}

export function TrendsPerformanceTab({
  relTrends,
  trends,
  confidence,
  successRate,
  searchAnalytics,
  isLoading,
}: TrendsPerformanceTabProps) {
  return (
    <div className="space-y-6">
      {/* Historical Trend Chart */}
      <div className="grid grid-cols-1 gap-6">
        <ReliabilityTrendsChart trends={relTrends} isLoading={isLoading} />
      </div>

      {/* Confidence Distribution & Detailed Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
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
    </div>
  )
}
