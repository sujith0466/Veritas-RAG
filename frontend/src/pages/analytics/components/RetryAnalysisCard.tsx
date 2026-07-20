import { RefreshCcw, AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import type { SuccessRateDTO } from '@/types'

interface RetryAnalysisCardProps {
  successRate: SuccessRateDTO | null
  isLoading?: boolean
}

export function RetryAnalysisCard({ successRate, isLoading }: RetryAnalysisCardProps) {
  if (isLoading || !successRate) {
    return (
      <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
        <CardHeader>
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <RefreshCcw className="h-4.5 w-4.5 text-primary animate-spin" />
            Self-Correction & Retry Loop Analysis
          </CardTitle>
        </CardHeader>
        <CardContent className="h-[220px] flex items-center justify-center text-xs text-muted-foreground">
          Loading self-correction metrics...
        </CardContent>
      </Card>
    )
  }

  const {
    total_queries,
    success_count,
    clarification_count,
    failure_count,
    retry_count,
    avg_retries_per_query,
  } = successRate

  return (
    <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg flex flex-col justify-between">
      <CardHeader className="pb-3 border-b border-border/40">
        <CardTitle className="text-base font-bold flex items-center gap-2">
          <RefreshCcw className="h-4.5 w-4.5 text-primary" />
          Self-Correction & Retry Loop Analysis
        </CardTitle>
        <CardDescription className="text-xs text-muted-foreground mt-0.5">
          Query rewrite loop interventions, clarification prompts, and hallucination prevention
        </CardDescription>
      </CardHeader>

      <CardContent className="pt-5 space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-surface/80 border border-border/50 p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Average Retries / Query</span>
              <RefreshCcw className="h-3.5 w-3.5 text-primary" />
            </div>
            <div className="text-xl font-bold text-foreground">
              {avg_retries_per_query.toFixed(2)}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              Query rewrite attempts
            </div>
          </div>

          <div className="rounded-lg bg-surface/80 border border-border/50 p-3">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Queries with Retries</span>
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            </div>
            <div className="text-xl font-bold text-foreground">
              {retry_count}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              {total_queries > 0 ? `${((retry_count / total_queries) * 100).toFixed(1)}% of total` : '0.0%'}
            </div>
          </div>
        </div>

        <div className="space-y-3 pt-1">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              <span className="font-medium text-foreground">Direct Success / Safe to Serve</span>
            </div>
            <span className="font-semibold text-emerald-500">{success_count} queries</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4 text-amber-500 shrink-0" />
              <span className="font-medium text-foreground">Clarification Required (Ambiguous)</span>
            </div>
            <span className="font-semibold text-amber-500">{clarification_count} queries</span>
          </div>

          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-rose-500 shrink-0" />
              <span className="font-medium text-foreground">Aborted (Hallucination / Low Conf)</span>
            </div>
            <span className="font-semibold text-rose-500">{failure_count} queries</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
