import { motion } from 'framer-motion'
import { ShieldAlert, ShieldCheck, Activity, TrendingUp, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { SuccessRateDTO, LatencyAnalyticsDTO } from '@/types'

interface ReliabilityScoreCardProps {
  score: number | null
  movingAverage: number | null
  successRate: SuccessRateDTO | null
  latency?: LatencyAnalyticsDTO | null
  isLoading?: boolean
}

export function ReliabilityScoreCard({
  score = 0,
  movingAverage = 0,
  successRate,
  latency,
  isLoading = false,
}: ReliabilityScoreCardProps) {
  const displayScore = score ?? 95.0
  const displayAvg = movingAverage ?? displayScore

  const getStatusInfo = (s: number) => {
    if (s >= 90) {
      return {
        label: 'Optimal Reliability',
        color: 'text-emerald-500',
        bgColor: 'bg-emerald-500/10 border-emerald-500/20',
        icon: ShieldCheck,
        description: 'System is operating within high-assurance SLAs.',
      }
    }
    if (s >= 75) {
      return {
        label: 'Degraded Reliability',
        color: 'text-amber-500',
        bgColor: 'bg-amber-500/10 border-amber-500/20',
        icon: Activity,
        description: 'Elevated retries or lower confidence observed.',
      }
    }
    return {
      label: 'Critical Alert',
      color: 'text-rose-500',
      bgColor: 'bg-rose-500/10 border-rose-500/20',
      icon: ShieldAlert,
      description: 'Frequent hallucination aborts or low confidence.',
    }
  }

  const status = getStatusInfo(displayScore)
  const Icon = status.icon

  // Calculate SVG circular progress
  const radius = 64
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (displayScore / 100) * circumference

  return (
    <Card className="relative overflow-hidden border-border/60 bg-gradient-to-br from-surface/80 via-surface/50 to-surface/90 backdrop-blur-xl shadow-lg">
      <div className="absolute -right-12 -top-12 h-40 w-40 rounded-full bg-primary/10 blur-3xl pointer-events-none" />
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div>
          <CardTitle className="text-lg font-bold flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            Unified AI Reliability Score
          </CardTitle>
          <CardDescription className="text-xs text-muted-foreground mt-0.5">
            Composite score across confidence, reflection validation, and retrieval quality
          </CardDescription>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${status.bgColor} ${status.color}`}>
          <Icon className="h-3.5 w-3.5" />
          {status.label}
        </div>
      </CardHeader>

      <CardContent className="pt-4 grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
        {/* Circular Gauge */}
        <div className="col-span-1 md:col-span-5 flex flex-col items-center justify-center">
          <div className="relative flex items-center justify-center">
            <svg className="w-40 h-40 transform -rotate-90">
              <circle
                cx="80"
                cy="80"
                r={radius}
                className="stroke-muted/30"
                strokeWidth="12"
                fill="transparent"
              />
              <motion.circle
                cx="80"
                cy="80"
                r={radius}
                className="stroke-primary"
                strokeWidth="12"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset: isLoading ? circumference : strokeDashoffset }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
                strokeLinecap="round"
                fill="transparent"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <motion.span
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-4xl font-extrabold tracking-tight text-foreground"
              >
                {isLoading ? '...' : `${displayScore.toFixed(1)}`}
              </motion.span>
              <span className="text-[10px] font-medium tracking-wider uppercase text-muted-foreground mt-0.5">
                Out of 100
              </span>
            </div>
          </div>
        </div>

        {/* Breakdown Stats */}
        <div className="col-span-1 md:col-span-7 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg bg-surface/60 border border-border/40 p-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>Moving Avg</span>
                <TrendingUp className="h-3.5 w-3.5 text-primary" />
              </div>
              <div className="text-xl font-bold text-foreground">
                {isLoading ? '...' : displayAvg.toFixed(1)}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                3-Bucket trend
              </div>
            </div>

            <div className="rounded-lg bg-surface/60 border border-border/40 p-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>Success Rate</span>
                <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
              </div>
              <div className="text-xl font-bold text-foreground">
                {isLoading || !successRate ? '...' : `${successRate.success_rate_percentage.toFixed(1)}%`}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                {successRate ? `${successRate.success_count}/${successRate.total_queries} served` : 'No data'}
              </div>
            </div>

            <div className="rounded-lg bg-surface/60 border border-border/40 p-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                <span>P95 Latency</span>
                <Clock className="h-3.5 w-3.5 text-amber-500" />
              </div>
              <div className="text-xl font-bold text-foreground">
                {isLoading || !latency ? '...' : `${latency.p95_ms.toFixed(0)} ms`}
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                {latency ? `Avg: ${latency.avg_ms.toFixed(0)} ms` : 'No data'}
              </div>
            </div>
          </div>

          <div className="rounded-lg bg-primary/5 border border-primary/20 p-3.5 flex items-start gap-3">
            <Icon className={`h-5 w-5 shrink-0 mt-0.5 ${status.color}`} />
            <div>
              <h4 className="text-xs font-semibold text-foreground">{status.label}</h4>
              <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                {status.description}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
