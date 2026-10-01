import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Users, FileText, Activity, ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import type { WorkspaceOverviewDTO, SuccessRateDTO } from '@/types'

interface ExecutiveKpiGridProps {
  overview?: WorkspaceOverviewDTO
  successRate?: SuccessRateDTO
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

interface KpiItemProps {
  title: string
  value: string | number
  unit?: string
  description: string
  icon: React.ReactNode
  accentColor: 'blue' | 'emerald' | 'purple' | 'cyan'
  sparklineData?: number[]
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  delayIndex: number
}

export function ExecutiveKpiGrid({
  overview,
  successRate,
  isLoading,
  isError,
  onRetry,
}: ExecutiveKpiGridProps) {
  // Format reliability percentage or show honest empty state
  const reliabilityValue = React.useMemo(() => {
    if (!successRate || successRate.total_queries === 0) {
      return { val: '—', desc: 'No queries in this window' }
    }
    return {
      val: `${successRate.success_rate_percentage.toFixed(1)}%`,
      desc: `${successRate.success_count} grounded / ${successRate.total_queries} total`,
    }
  }, [successRate])

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Active Users */}
      <KpiCard
        title="Active Users"
        value={overview?.active_users ?? 0}
        description="Users engaging with RAG chat in period"
        icon={<Users className="w-5 h-5 text-blue-400" />}
        accentColor="blue"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
        delayIndex={0}
      />

      {/* 2. Knowledge Documents */}
      <KpiCard
        title="Indexed Documents"
        value={overview?.document_count ?? 0}
        description="Ready documents available for vector search"
        icon={<FileText className="w-5 h-5 text-emerald-400" />}
        accentColor="emerald"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
        delayIndex={1}
      />

      {/* 3. Total Queries */}
      <KpiCard
        title="Total Invocations"
        value={overview?.total_queries ?? 0}
        description="RAG retrieval and generation requests"
        icon={<Activity className="w-5 h-5 text-purple-400" />}
        accentColor="purple"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
        delayIndex={2}
      />

      {/* 4. Grounded Reliability Rate */}
      <KpiCard
        title="Grounded Reliability"
        value={reliabilityValue.val}
        description={reliabilityValue.desc}
        icon={<ShieldCheck className="w-5 h-5 text-cyan-400" />}
        accentColor="cyan"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
        delayIndex={3}
      />
    </div>
  )
}

function KpiCard({
  title,
  value,
  description,
  icon,
  accentColor,
  isLoading,
  isError,
  onRetry,
  delayIndex,
}: KpiItemProps) {
  const shouldReduceMotion = useReducedMotion()

  const accentStyles = {
    blue: {
      border: 'hover:border-blue-500/40',
      glow: 'group-hover:shadow-[0_0_25px_rgba(59,130,246,0.12)]',
      iconBg: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      bar: 'bg-gradient-to-r from-blue-500 to-indigo-500',
    },
    emerald: {
      border: 'hover:border-emerald-500/40',
      glow: 'group-hover:shadow-[0_0_25px_rgba(16,185,129,0.12)]',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      bar: 'bg-gradient-to-r from-emerald-500 to-teal-500',
    },
    purple: {
      border: 'hover:border-purple-500/40',
      glow: 'group-hover:shadow-[0_0_25px_rgba(168,85,247,0.12)]',
      iconBg: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      bar: 'bg-gradient-to-r from-purple-500 to-violet-500',
    },
    cyan: {
      border: 'hover:border-cyan-500/40',
      glow: 'group-hover:shadow-[0_0_25px_rgba(6,182,212,0.12)]',
      iconBg: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
      bar: 'bg-gradient-to-r from-cyan-500 to-blue-500',
    },
  }[accentColor]

  return (
    <motion.div
      initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: shouldReduceMotion ? 0.1 : 0.35, delay: shouldReduceMotion ? 0 : delayIndex * 0.08 }}
      className="group"
    >
      <Card
        className={`relative h-full overflow-hidden border border-border/60 bg-card/60 dark:bg-slate-900/60 backdrop-blur-xl transition-all duration-300 ${accentStyles.border} ${accentStyles.glow} rounded-2xl`}
      >
        {/* Subtle top accent highlight */}
        <div className={`h-1 w-full ${accentStyles.bar}`} />

        <CardContent className="p-5 flex flex-col justify-between h-[calc(100%-4px)] gap-4">
          <div className="flex items-start justify-between gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
              {title}
            </span>
            <div
              className={`p-2 rounded-xl border transition-transform duration-300 group-hover:scale-110 ${accentStyles.iconBg}`}
            >
              {icon}
            </div>
          </div>

          <div>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-24 rounded-lg" />
                <Skeleton className="h-3 w-36 rounded" />
              </div>
            ) : isError ? (
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5 text-xs text-destructive">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>Failed to load</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onRetry}
                  className="h-6 px-2 text-[11px] gap-1 text-muted-foreground hover:text-foreground"
                >
                  <RefreshCw className="w-3 h-3" />
                  Retry
                </Button>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground font-mono">
                  {typeof value === 'number' ? value.toLocaleString() : value}
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1" title={description}>
                  {description}
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
