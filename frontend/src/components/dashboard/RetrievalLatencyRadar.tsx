import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Clock, PieChart } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { CommandLatencyPercentilesDTO, CommandOutcomesBreakdownDTO } from '@/types'

interface RetrievalLatencyRadarProps {
  latency: CommandLatencyPercentilesDTO
  outcomes: CommandOutcomesBreakdownDTO
  isLoading: boolean
}

export const RetrievalLatencyRadar: React.FC<RetrievalLatencyRadarProps> = ({
  latency,
  outcomes,
  isLoading,
}) => {
  const shouldReduceMotion = useReducedMotion()
  const percentiles = [
    { label: 'P50 Median', value: latency.p50_ms, target: '< 1.5s' },
    { label: 'P90 Percentile', value: latency.p90_ms, target: '< 5s' },
    { label: 'P95 Percentile', value: latency.p95_ms, target: '< 10s' },
    { label: 'P99 Tail', value: latency.p99_ms, target: '< 20s' },
  ]

  const total = outcomes.total_count || 1
  const successPct = Math.round((outcomes.success_count / total) * 100)
  const clarifPct = Math.round((outcomes.clarification_count / total) * 100)
  const abortPct = Math.round(
    ((outcomes.aborted_hallucination_count + outcomes.aborted_low_confidence_count) / total) * 100
  )
  const otherPct = Math.max(0, 100 - (successPct + clarifPct + abortPct))

  return (
    <Card className="bg-card/60 backdrop-blur-md border border-border/70 shadow-sm flex flex-col h-full">
      <CardHeader className="pb-3 border-b border-border/40">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400" />
              Latency Decomposition & SLA Compliance
            </CardTitle>
            <CardDescription className="text-xs">
              Measured response distribution and execution outcome proportions.
            </CardDescription>
          </div>
          <span className="text-[11px] font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
            Avg: {isLoading ? '...' : latency.avg_ms !== null ? `${Math.round(latency.avg_ms)}ms` : 'N/A'}
          </span>
        </div>
      </CardHeader>

      <CardContent className="p-4 flex-1 flex flex-col justify-between space-y-4">
        {/* Latency Percentile Bars */}
        <div className="space-y-3">
          {percentiles.map((p) => {
            const val = p.value
            const hasVal = typeof val === 'number'
            const ms = hasVal ? Math.round(val) : 0
            // Normalized representation for visual bar (up to 30,000ms max scale)
            const barWidth = hasVal ? Math.min(100, Math.max(8, (ms / 30000) * 100)) : 0

            return (
              <div key={p.label} className="text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-foreground">{p.label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">Target {p.target}</span>
                    <span className="font-mono font-bold text-foreground">
                      {hasVal ? `${ms.toLocaleString()} ms` : 'N/A'}
                    </span>
                  </div>
                </div>
                <div className="h-2 w-full bg-muted/60 rounded-full overflow-hidden">
                  <motion.div
                    initial={shouldReduceMotion ? false : { width: 0 }}
                    animate={{ width: `${barWidth}%` }}
                    transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                    className={`h-full rounded-full ${
                      ms < 2000 ? 'bg-emerald-500' : ms < 10000 ? 'bg-amber-500' : 'bg-rose-500'
                    }`}
                  />
                </div>
              </div>
            )
          })}
        </div>

        {/* Outcomes Ratio Breakdown */}
        <div className="pt-3 border-t border-border/40 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-foreground flex items-center gap-1.5">
              <PieChart className="h-3.5 w-3.5 text-primary" />
              Outcome Distribution
            </span>
            <span className="font-mono text-muted-foreground">{outcomes.total_count} total</span>
          </div>

          {/* Stacked Progress Bar */}
          <div className="h-2.5 w-full bg-muted rounded-full overflow-hidden flex">
            <motion.div
              initial={shouldReduceMotion ? false : { width: 0 }}
              animate={{ width: `${successPct}%` }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="bg-emerald-500 h-full"
              title={`Success: ${outcomes.success_count}`}
            />
            <motion.div
              initial={shouldReduceMotion ? false : { width: 0 }}
              animate={{ width: `${clarifPct}%` }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="bg-sky-500 h-full"
              title={`Clarifications: ${outcomes.clarification_count}`}
            />
            <motion.div
              initial={shouldReduceMotion ? false : { width: 0 }}
              animate={{ width: `${abortPct}%` }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="bg-amber-500 h-full"
              title={`Aborted/Intervened: ${outcomes.aborted_hallucination_count + outcomes.aborted_low_confidence_count}`}
            />
            <motion.div
              initial={shouldReduceMotion ? false : { width: 0 }}
              animate={{ width: `${otherPct}%` }}
              transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
              className="bg-slate-600 h-full"
              title="Other / Unclassified"
            />
          </div>

          {/* Legend */}
          <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 flex-wrap gap-2">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
              Success ({outcomes.success_count})
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-sky-500 inline-block" />
              Clarification ({outcomes.clarification_count})
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
              Safety Aborts ({outcomes.aborted_hallucination_count + outcomes.aborted_low_confidence_count})
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
