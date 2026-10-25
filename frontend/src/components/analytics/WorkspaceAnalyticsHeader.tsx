import { motion, useReducedMotion } from 'framer-motion'
import { RefreshCw } from 'lucide-react'
import { Button } from '@/components/common/Button'

export type AnalyticsTimeRange = '24h' | '7d' | '30d' | '90d' | 'all'

interface WorkspaceAnalyticsHeaderProps {
  timeRange: AnalyticsTimeRange
  onTimeRangeChange: (range: AnalyticsTimeRange) => void
  onRefresh: () => void
  isRefreshing: boolean
  lastUpdated: Date | null
  workspaceName?: string
  workspaceStatus?: string
}

const TIME_RANGE_OPTIONS: { id: AnalyticsTimeRange; label: string }[] = [
  { id: '24h', label: '24H' },
  { id: '7d', label: '7D' },
  { id: '30d', label: '30D' },
  { id: '90d', label: '90D' },
  { id: 'all', label: 'All Time' },
]

export function WorkspaceAnalyticsHeader({
  timeRange,
  onTimeRangeChange,
  onRefresh,
  isRefreshing,
  lastUpdated,
  workspaceName: _workspaceName = 'Active Workspace',
  workspaceStatus: _workspaceStatus = 'ACTIVE',
}: WorkspaceAnalyticsHeaderProps) {
  const shouldReduceMotion = useReducedMotion()

  const formatLastUpdated = (date: Date | null) => {
    if (!date) return 'Just now'
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div className="flex flex-col gap-6 pb-2 border-b border-border/40">
      {/* Top row: Context & Title */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="space-y-1.5">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <span>Knowledge Reliability & Intelligence</span>
          </h1>

          <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
            Real-time telemetry, knowledge asset citation impact, query forensics, and staleness diagnostics
            scoped strictly to this workspace.
          </p>
        </div>

        {/* Action controls: Time selector & Refresh */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Time range pill selector */}
          <div
            role="group"
            aria-label="Analytics time range filter"
            className="flex items-center bg-card/80 dark:bg-surface/80 p-1 rounded-xl border border-border/60 shadow-sm"
          >
            {TIME_RANGE_OPTIONS.map((opt) => {
              const isSelected = timeRange === opt.id
              return (
                <button
                  key={opt.id}
                  onClick={() => onTimeRangeChange(opt.id)}
                  aria-pressed={isSelected}
                  className={`relative px-3 py-1.5 text-xs font-medium rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    isSelected
                      ? 'text-primary-foreground font-semibold'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
                  }`}
                >
                  {isSelected && (
                    <motion.div
                      layoutId="activeTimeRange"
                      transition={
                        shouldReduceMotion
                          ? { duration: 0 }
                          : { type: 'spring', stiffness: 450, damping: 35 }
                      }
                      className="absolute inset-0 bg-primary rounded-lg shadow-sm"
                    />
                  )}
                  <span className="relative z-10">{opt.label}</span>
                </button>
              )
            })}
          </div>

          {/* Manual refresh button */}
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="h-9 px-3 gap-2 bg-card/80 dark:bg-surface/80 border-border/60 hover:bg-muted/60"
            title="Refresh analytics data"
            aria-label="Refresh workspace analytics"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-primary' : 'text-muted-foreground'}`}
            />
            <span className="hidden sm:inline text-xs font-medium">
              {isRefreshing ? 'Syncing...' : 'Refresh'}
            </span>
          </Button>
        </div>
      </div>

      {/* Supporting meta row */}
      <div className="flex items-center justify-end text-xs text-muted-foreground/80 pt-1">
        <div className="flex items-center gap-1 text-[11px]">
          <span>Telemetry synced at:</span>
          <span className="font-mono text-muted-foreground font-medium">{formatLastUpdated(lastUpdated)}</span>
        </div>
      </div>
    </div>
  )
}
