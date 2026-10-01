import React from 'react'
import { Activity, FileText, Zap, ShieldAlert } from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import type { CommandKpisDTO, CommandReliabilityTrendPointDTO } from '@/types'

interface ExecutiveKpiGridProps {
  kpis: CommandKpisDTO
  trendPoints: CommandReliabilityTrendPointDTO[]
  timeWindow: string
  isLoading: boolean
}

export const ExecutiveKpiGrid: React.FC<ExecutiveKpiGridProps> = ({
  kpis,
  trendPoints,
  timeWindow,
  isLoading,
}) => {
  const hasQueries = kpis.total_queries > 0

  // Lightweight native SVG sparkline generator
  const renderSparkline = () => {
    if (!trendPoints || trendPoints.length < 2) return null
    const minVal = Math.min(...trendPoints.map((p) => p.reliability))
    const maxVal = Math.max(...trendPoints.map((p) => p.reliability))
    const range = maxVal - minVal || 1
    const width = 80
    const height = 24

    const points = trendPoints
      .map((p, idx) => {
        const x = (idx / (trendPoints.length - 1)) * width
        const y = height - ((p.reliability - minVal) / range) * (height - 4) - 2
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')

    return (
      <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-primary/80"
          points={points}
        />
      </svg>
    )
  }

  const cards = [
    {
      title: 'Composite Reliability',
      value: isLoading
        ? '...'
        : hasQueries && kpis.avg_reliability_score !== null
        ? `${(kpis.avg_reliability_score * 100).toFixed(1)}%`
        : 'N/A',
      subtitle: hasQueries
        ? `Clarifications: ${kpis.clarification_rate.toFixed(1)}%`
        : 'No queries in window',
      icon: Activity,
      color: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
      valueColor:
        hasQueries && kpis.avg_reliability_score !== null && kpis.avg_reliability_score >= 0.8
          ? 'text-emerald-400'
          : hasQueries
          ? 'text-amber-400'
          : 'text-muted-foreground',
    },
    {
      title: `Query Volume (${timeWindow.toUpperCase()})`,
      value: isLoading ? '...' : kpis.total_queries.toLocaleString(),
      subtitle:
        hasQueries && kpis.avg_confidence_score !== null
          ? `Avg Confidence: ${(kpis.avg_confidence_score * 100).toFixed(1)}%`
          : 'Zero query activity recorded',
      icon: FileText,
      color: 'text-sky-500 bg-sky-500/10 border-sky-500/20',
      valueColor: 'text-foreground',
      extra: renderSparkline(),
    },
    {
      title: 'P95 Execution Latency',
      value: isLoading
        ? '...'
        : hasQueries && kpis.p95_latency_ms !== null
        ? `${Math.round(kpis.p95_latency_ms).toLocaleString()} ms`
        : 'N/A',
      subtitle:
        hasQueries && kpis.avg_latency_ms !== null
          ? `Avg: ${Math.round(kpis.avg_latency_ms).toLocaleString()} ms`
          : 'Awaiting telemetry samples',
      icon: Zap,
      color: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
      valueColor:
        hasQueries && kpis.p95_latency_ms !== null && kpis.p95_latency_ms < 3000
          ? 'text-emerald-400'
          : hasQueries && kpis.p95_latency_ms !== null && kpis.p95_latency_ms < 10000
          ? 'text-amber-400'
          : hasQueries
          ? 'text-rose-400'
          : 'text-muted-foreground',
    },
    {
      title: 'Self-Correction Rate',
      value: isLoading
        ? '...'
        : hasQueries
        ? `${kpis.self_correction_rate.toFixed(1)}%`
        : '0.0%',
      subtitle: `${kpis.hallucination_prevention_count} safety interventions triggered`,
      icon: ShieldAlert,
      color: 'text-indigo-500 bg-indigo-500/10 border-indigo-500/20',
      valueColor: 'text-foreground',
    },
  ]

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((c) => (
        <Card
          key={c.title}
          className="relative overflow-hidden bg-card/60 backdrop-blur-md border border-border/70 hover:border-border transition-all duration-200 shadow-sm"
        >
          <CardContent className="p-5">
            <div className="flex items-center justify-between pb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {c.title}
              </span>
              <div className={`p-2 rounded-lg border ${c.color}`}>
                <c.icon className="h-4 w-4" />
              </div>
            </div>

            <div className="flex items-baseline justify-between gap-2">
              <span className={`text-2xl sm:text-3xl font-extrabold font-mono tracking-tight ${c.valueColor}`}>
                {c.value}
              </span>
              {c.extra && <div className="shrink-0">{c.extra}</div>}
            </div>

            <p className="text-xs text-muted-foreground mt-2 truncate font-medium">
              {c.subtitle}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
