import { useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, BarChart3 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { ConfidenceAnalyticsDTO, QueryTrendsDTO } from '@/types'

interface ConfidenceTrendsChartProps {
  trends: QueryTrendsDTO | null
  distribution: ConfidenceAnalyticsDTO | null
  isLoading?: boolean
}

export function ConfidenceTrendsChart({ trends, distribution, isLoading }: ConfidenceTrendsChartProps) {
  const [activeTab, setActiveTab] = useState<'trends' | 'distribution'>('trends')

  const timestamps = trends?.timestamps || []
  const confScores = trends?.avg_confidence_scores || []
  const relScores = trends?.avg_reliability_scores || []

  return (
    <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <TrendingUp className="h-4.5 w-4.5 text-primary" />
            Confidence & Reliability Dynamics
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-0.5">
            Pre-generation confidence score distribution and historical trend correlation
          </CardDescription>
        </div>

        <div className="flex items-center gap-1 bg-surface/80 p-1 rounded-lg border border-border/50 self-start sm:self-auto">
          <button
            onClick={() => setActiveTab('trends')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === 'trends'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Time-Series Trends
          </button>
          <button
            onClick={() => setActiveTab('distribution')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              activeTab === 'distribution'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Score Distribution
          </button>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        {isLoading ? (
          <div className="flex h-[260px] items-center justify-center">
            <div className="flex flex-col items-center gap-2 text-muted-foreground text-xs animate-pulse">
              <BarChart3 className="h-8 w-8 text-primary/60 animate-bounce" />
              Loading analytical trends...
            </div>
          </div>
        ) : activeTab === 'trends' ? (
          <div className="space-y-4">
            {timestamps.length === 0 ? (
              <div className="flex h-[240px] items-center justify-center border-2 border-dashed border-border/50 rounded-lg text-xs text-muted-foreground">
                No historical trend data available for this date range yet.
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-end gap-4 text-xs font-medium mb-3">
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-primary" />
                    <span className="text-muted-foreground">Avg Confidence (0 - 1.0)</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span className="text-muted-foreground">Reliability Score (0 - 100)</span>
                  </div>
                </div>

                {/* Custom SVG Bar/Trend Chart */}
                <div className="relative h-[220px] w-full pt-4 pb-6 px-2 flex items-end justify-between gap-2 border-b border-border/50">
                  {timestamps.map((ts, idx) => {
                    const conf = confScores[idx] || 0
                    const rel = relScores[idx] || 0
                    const confHeightPct = Math.min(Math.max(conf * 100, 4), 100)
                    const relHeightPct = Math.min(Math.max(rel, 4), 100)

                    return (
                      <div key={ts} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group relative">
                        {/* Tooltip on hover */}
                        <div className="absolute -top-12 opacity-0 group-hover:opacity-100 transition-opacity bg-surface border border-border px-2 py-1 rounded text-[10px] whitespace-nowrap shadow-md pointer-events-none z-10">
                          <div className="font-semibold">{ts}</div>
                          <div className="text-primary">Conf: {conf.toFixed(2)}</div>
                          <div className="text-emerald-500">Reliability: {rel.toFixed(1)}</div>
                        </div>

                        <div className="w-full flex items-end justify-center gap-1 h-full">
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: `${confHeightPct}%` }}
                            transition={{ duration: 0.6, delay: idx * 0.05 }}
                            className="w-3.5 sm:w-5 bg-gradient-to-t from-primary/80 to-primary rounded-t-sm shadow-sm"
                          />
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: `${relHeightPct}%` }}
                            transition={{ duration: 0.6, delay: idx * 0.05 + 0.1 }}
                            className="w-3.5 sm:w-5 bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-sm shadow-sm opacity-90"
                          />
                        </div>
                        <span className="text-[10px] text-muted-foreground truncate max-w-[50px] mt-1">
                          {ts.split('T')[0].split('-').slice(1).join('/')}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {/* Confidence Breakdown Bars */}
            {!distribution || (distribution.high_confidence_count + distribution.medium_confidence_count + distribution.low_confidence_count) === 0 ? (
              <div className="flex h-[240px] items-center justify-center border-2 border-dashed border-border/50 rounded-lg text-xs text-muted-foreground">
                No pre-generation confidence score records found yet.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                <div className="col-span-1 md:col-span-7 space-y-4">
                  <div>
                    <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                      <span className="text-emerald-500 flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        High Confidence (&ge; 0.75)
                      </span>
                      <span className="text-foreground font-bold">{distribution.high_confidence_count} queries</span>
                    </div>
                    <div className="h-2.5 w-full bg-surface rounded-full overflow-hidden border border-border/40">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{
                          width: `${(distribution.high_confidence_count / Math.max(1, distribution.high_confidence_count + distribution.medium_confidence_count + distribution.low_confidence_count)) * 100}%`,
                        }}
                        transition={{ duration: 0.8 }}
                        className="h-full bg-emerald-500 rounded-full"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                      <span className="text-amber-500 flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-amber-500" />
                        Medium Confidence (0.40 &ndash; 0.74)
                      </span>
                      <span className="text-foreground font-bold">{distribution.medium_confidence_count} queries</span>
                    </div>
                    <div className="h-2.5 w-full bg-surface rounded-full overflow-hidden border border-border/40">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{
                          width: `${(distribution.medium_confidence_count / Math.max(1, distribution.high_confidence_count + distribution.medium_confidence_count + distribution.low_confidence_count)) * 100}%`,
                        }}
                        transition={{ duration: 0.8, delay: 0.1 }}
                        className="h-full bg-amber-500 rounded-full"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between text-xs font-semibold mb-1.5">
                      <span className="text-rose-500 flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-rose-500" />
                        Low Confidence (&lt; 0.40) &mdash; Abort Threshold
                      </span>
                      <span className="text-foreground font-bold">{distribution.low_confidence_count} queries</span>
                    </div>
                    <div className="h-2.5 w-full bg-surface rounded-full overflow-hidden border border-border/40">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{
                          width: `${(distribution.low_confidence_count / Math.max(1, distribution.high_confidence_count + distribution.medium_confidence_count + distribution.low_confidence_count)) * 100}%`,
                        }}
                        transition={{ duration: 0.8, delay: 0.2 }}
                        className="h-full bg-rose-500 rounded-full"
                      />
                    </div>
                  </div>
                </div>

                {/* KPI Summary Cards */}
                <div className="col-span-1 md:col-span-5 grid grid-cols-3 gap-3">
                  <div className="rounded-lg bg-surface/80 border border-border/50 p-3 text-center">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase">Average</span>
                    <div className="text-lg font-bold text-primary mt-1">
                      {distribution.avg_confidence.toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-surface/80 border border-border/50 p-3 text-center">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase">Minimum</span>
                    <div className="text-lg font-bold text-rose-500 mt-1">
                      {distribution.min_confidence.toFixed(2)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-surface/80 border border-border/50 p-3 text-center">
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase">Maximum</span>
                    <div className="text-lg font-bold text-emerald-500 mt-1">
                      {distribution.max_confidence.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
