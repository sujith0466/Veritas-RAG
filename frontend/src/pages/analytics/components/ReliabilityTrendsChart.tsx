import { motion } from 'framer-motion'
import { TrendingUp, BarChart3 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { ReliabilityTrendDTO } from '@/types'

interface ReliabilityTrendsChartProps {
  trends: ReliabilityTrendDTO[] | null
  isLoading?: boolean
}

export function ReliabilityTrendsChart({ trends, isLoading }: ReliabilityTrendsChartProps) {
  return (
    <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
      <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/40">
        <div>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <TrendingUp className="h-4.5 w-4.5 text-emerald-500" />
            Reliability Score Trends
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-0.5">
            Daily average reliability score evolution over time
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        {isLoading ? (
          <div className="flex h-[260px] items-center justify-center">
            <div className="flex flex-col items-center gap-2 text-muted-foreground text-xs animate-pulse">
              <BarChart3 className="h-8 w-8 text-primary/60 animate-bounce" />
              Loading reliability trends...
            </div>
          </div>
        ) : !trends || trends.length === 0 ? (
          <div className="flex h-[240px] items-center justify-center border-2 border-dashed border-border/50 rounded-lg text-xs text-muted-foreground">
            No historical trend data available for this date range yet.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-end gap-4 text-xs font-medium mb-3">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                <span className="text-muted-foreground">Reliability Score (0 - 100)</span>
              </div>
            </div>

            {/* Custom SVG Bar/Trend Chart */}
            <div className="relative h-[220px] w-full pt-4 pb-6 px-2 flex items-end justify-between gap-2 border-b border-border/50">
              {trends.map((t, idx) => {
                const rel = t.average_score
                const relHeightPct = Math.min(Math.max(rel, 4), 100)

                return (
                  <div key={t.date} className="flex-1 flex flex-col items-center gap-1.5 h-full justify-end group relative">
                    {/* Tooltip on hover */}
                    <div className="absolute -top-12 opacity-0 group-hover:opacity-100 transition-opacity bg-surface border border-border px-2 py-1 rounded text-[10px] whitespace-nowrap shadow-md pointer-events-none z-10">
                      <div className="font-semibold">{t.date}</div>
                      <div className="text-emerald-500">Reliability: {rel.toFixed(1)}</div>
                    </div>

                    <div className="w-full flex items-end justify-center gap-1 h-full">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${relHeightPct}%` }}
                        transition={{ duration: 0.6, delay: idx * 0.05 }}
                        className="w-3.5 sm:w-5 bg-gradient-to-t from-emerald-600 to-emerald-400 rounded-t-sm shadow-sm opacity-90"
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground truncate max-w-[50px] mt-1">
                      {t.date.split('-').slice(1).join('/')}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
