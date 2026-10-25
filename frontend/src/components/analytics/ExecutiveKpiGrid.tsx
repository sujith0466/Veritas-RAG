import React from 'react'
import { motion } from 'framer-motion'
import { Users, FileText, Activity, ShieldCheck, AlertCircle, RefreshCw } from 'lucide-react'
import { Card, CardContent } from '@/components/common/Card'
import { Skeleton } from '@/components/common/Skeleton'
import { Button } from '@/components/common/Button'
import { workspaceCardGroupVariants, workspaceCardItemVariants } from '@/motion'
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
  accentColor: 'champagne' | 'emerald' | 'teal' | 'primary'
  sparklineData?: number[]
  isLoading: boolean
  isError: boolean
  onRetry: () => void
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
    <motion.div
      variants={workspaceCardGroupVariants}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
    >
      {/* 1. Active Users */}
      <KpiCard
        title="Active Users"
        value={overview?.active_users ?? 0}
        description="Users engaging with RAG chat in period"
        icon={<Users className="w-5 h-5 text-champagne" />}
        accentColor="champagne"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
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
      />

      {/* 3. Total Queries */}
      <KpiCard
        title="Total Invocations"
        value={overview?.total_queries ?? 0}
        description="RAG retrieval and generation requests"
        icon={<Activity className="w-5 h-5 text-primary" />}
        accentColor="teal"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
      />

      {/* 4. Grounded Reliability Rate */}
      <KpiCard
        title="Grounded Reliability"
        value={reliabilityValue.val}
        description={reliabilityValue.desc}
        icon={<ShieldCheck className="w-5 h-5 text-primary" />}
        accentColor="primary"
        isLoading={isLoading}
        isError={isError}
        onRetry={onRetry}
      />
    </motion.div>
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
}: KpiItemProps) {
  const accentStyles = {
    champagne: {
      border: 'hover:border-champagne/40',
      glow: 'group-hover:shadow-[0_0_20px_rgba(179,154,112,0.12)]',
      iconBg: 'bg-champagne/10 text-champagne border-champagne/20',
      bar: 'bg-gradient-to-r from-champagne/90 to-champagne/40',
    },
    emerald: {
      border: 'hover:border-emerald-500/40',
      glow: 'group-hover:shadow-[0_0_20px_rgba(16,185,129,0.12)]',
      iconBg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      bar: 'bg-gradient-to-r from-emerald-500 to-teal-500',
    },
    teal: {
      border: 'hover:border-primary/40',
      glow: 'group-hover:shadow-[0_0_20px_rgba(69,175,162,0.12)]',
      iconBg: 'bg-primary/10 text-primary border-primary/20',
      bar: 'bg-gradient-to-r from-primary to-primary/50',
    },
    primary: {
      border: 'hover:border-primary/40',
      glow: 'group-hover:shadow-[0_0_20px_rgba(69,175,162,0.12)]',
      iconBg: 'bg-primary/10 text-primary border-primary/20',
      bar: 'bg-gradient-to-r from-primary to-emerald-500/80',
    },
  }[accentColor]

  return (
    <motion.div
      variants={workspaceCardItemVariants}
      className="group"
    >
      <Card
        className={`relative h-full overflow-hidden border border-border/60 bg-card/60 dark:bg-surface/60 backdrop-blur-xl transition-all duration-300 ${accentStyles.border} ${accentStyles.glow} rounded-2xl`}
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
