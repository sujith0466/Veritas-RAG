import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { TrendingUp, Clock, AlertCircle, RefreshCw, BarChart2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import type { ReliabilityTrendDTO, LatencyAnalyticsDTO } from '@/types'

interface WorkspaceActivityChartProps {
  trends?: ReliabilityTrendDTO[]
  latency?: LatencyAnalyticsDTO
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function WorkspaceActivityChart({
  trends = [],
  latency,
  isLoading,
  isError,
  onRetry,
}: WorkspaceActivityChartProps) {
  const shouldReduceMotion = useReducedMotion()
  const [hoveredPoint, setHoveredPoint] = React.useState<ReliabilityTrendDTO | null>(null)

  const hasData = trends.length > 0

  // Calculate SVG dimensions and coordinate path
  const svgWidth = 600
  const svgHeight = 160
  const paddingX = 40
  const paddingY = 25

  const points = React.useMemo(() => {
    if (trends.length === 0) return []
    if (trends.length === 1) {
      return [
        {
          x: svgWidth / 2,
          y: svgHeight / 2,
          item: trends[0],
        },
      ]
    }

    const minScore = 0
    const maxScore = 100

    return trends.map((item, idx) => {
      const x = paddingX + (idx / (trends.length - 1)) * (svgWidth - 2 * paddingX)
      const normalizedScore = Math.max(0, Math.min(100, item.average_score))
      const y = svgHeight - paddingY - (normalizedScore / (maxScore - minScore)) * (svgHeight - 2 * paddingY)
      return { x, y, item }
    })
  }, [trends])

  const pathD = React.useMemo(() => {
    if (points.length < 2) return ''
    return points.reduce((acc, curr, idx) => {
      if (idx === 0) return `M ${curr.x} ${curr.y}`
      return `${acc} L ${curr.x} ${curr.y}`
    }, '')
  }, [points])

  const areaD = React.useMemo(() => {
    if (points.length < 2) return ''
    const first = points[0]
    const last = points[points.length - 1]
    const baseline = svgHeight - paddingY
    return `${pathD} L ${last.x} ${baseline} L ${first.x} ${baseline} Z`
  }, [points, pathD])

  return (
    <Card className="border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl rounded-2xl overflow-hidden shadow-sm">
      <CardHeader className="pb-3 border-b border-border/30">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                <TrendingUp className="w-4 h-4" />
              </div>
              <CardTitle className="text-base font-semibold text-foreground">
                Grounded Reliability & Latency Telemetry
              </CardTitle>
            </div>
            <CardDescription className="text-xs text-muted-foreground">
              Daily grounding reliability scores and server-side execution latency percentiles
            </CardDescription>
          </div>

          {latency && (
            <div className="flex items-center gap-2 text-xs font-mono bg-muted/40 px-3 py-1.5 rounded-lg border border-border/40">
              <Clock className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">P50:</span>
              <span className="text-foreground font-semibold">{latency.p50_ms.toFixed(0)}ms</span>
              <span className="text-muted-foreground/40">|</span>
              <span className="text-muted-foreground">P95:</span>
              <span className="text-foreground font-semibold">{latency.p95_ms.toFixed(0)}ms</span>
              <span className="text-muted-foreground/40">|</span>
              <span className="text-muted-foreground">Avg:</span>
              <span className="text-foreground font-semibold">{latency.avg_ms.toFixed(0)}ms</span>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-4">
        {isLoading ? (
          <div className="h-44 w-full flex items-center justify-center">
            <Skeleton className="h-36 w-full rounded-xl" />
          </div>
        ) : isError ? (
          <div className="h-44 flex flex-col items-center justify-center text-center p-6 space-y-2">
            <AlertCircle className="w-8 h-8 text-destructive/70" />
            <p className="text-xs text-muted-foreground">Failed to load trend telemetry</p>
            <Button variant="outline" size="sm" onClick={onRetry} className="h-7 text-xs gap-1.5">
              <RefreshCw className="w-3 h-3" /> Retry
            </Button>
          </div>
        ) : !hasData ? (
          <div className="h-44 flex flex-col items-center justify-center text-center p-6 border border-dashed border-border/40 rounded-xl bg-background/30">
            <BarChart2 className="w-8 h-8 text-muted-foreground/40 mb-2" />
            <p className="text-xs font-medium text-foreground">No historical query activity in this period</p>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Run RAG queries in Chat to generate reliability telemetry for this workspace.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* SVG Interactive Line Chart */}
            <div className="relative w-full overflow-hidden">
              <svg
                viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                className="w-full h-40 overflow-visible"
                preserveAspectRatio="none"
              >
                <defs>
                  <linearGradient id="reliabilityGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {/* Horizontal reference grid lines */}
                <line
                  x1={paddingX}
                  y1={paddingY}
                  x2={svgWidth - paddingX}
                  y2={paddingY}
                  stroke="currentColor"
                  className="text-border/40"
                  strokeDasharray="4 4"
                />
                <line
                  x1={paddingX}
                  y1={svgHeight / 2}
                  x2={svgWidth - paddingX}
                  y2={svgHeight / 2}
                  stroke="currentColor"
                  className="text-border/40"
                  strokeDasharray="4 4"
                />
                <line
                  x1={paddingX}
                  y1={svgHeight - paddingY}
                  x2={svgWidth - paddingX}
                  y2={svgHeight - paddingY}
                  stroke="currentColor"
                  className="text-border/60"
                />

                {/* Y-axis labels */}
                <text x={paddingX - 8} y={paddingY + 4} textAnchor="end" className="text-[10px] fill-muted-foreground/60 font-mono">100%</text>
                <text x={paddingX - 8} y={svgHeight / 2 + 3} textAnchor="end" className="text-[10px] fill-muted-foreground/60 font-mono">50%</text>
                <text x={paddingX - 8} y={svgHeight - paddingY + 3} textAnchor="end" className="text-[10px] fill-muted-foreground/60 font-mono">0%</text>

                {/* Filled gradient area */}
                {areaD && (
                  <path d={areaD} fill="url(#reliabilityGradient)" />
                )}

                {/* Line path */}
                {pathD && (
                  <motion.path
                    d={pathD}
                    fill="none"
                    stroke="#06b6d4"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={shouldReduceMotion ? { pathLength: 1 } : { pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: shouldReduceMotion ? 0 : 0.8, ease: 'easeOut' }}
                  />
                )}

                {/* Data point dots */}
                {points.map((pt, i) => (
                  <circle
                    key={i}
                    cx={pt.x}
                    cy={pt.y}
                    r={hoveredPoint?.date === pt.item.date ? 5 : 3.5}
                    className={`transition-all duration-150 cursor-pointer ${
                      hoveredPoint?.date === pt.item.date
                        ? 'fill-cyan-400 stroke-background stroke-2'
                        : 'fill-cyan-500 hover:fill-cyan-300'
                    }`}
                    onMouseEnter={() => setHoveredPoint(pt.item)}
                    onMouseLeave={() => setHoveredPoint(null)}
                  />
                ))}
              </svg>

              {/* Floating hovered point tooltip */}
              {hoveredPoint && (
                <div className="absolute top-2 right-4 bg-popover/90 backdrop-blur-md border border-border px-3 py-1.5 rounded-lg shadow-lg text-xs font-mono">
                  <div className="text-muted-foreground text-[10px]">{hoveredPoint.date}</div>
                  <div className="text-cyan-400 font-bold">
                    Score: {hoveredPoint.average_score.toFixed(1)}%
                  </div>
                </div>
              )}
            </div>

            {/* X-axis date bounds */}
            <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground/70 px-2 pt-1">
              <span>{trends[0]?.date}</span>
              <span>{trends[trends.length - 1]?.date}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
