import React from 'react'
import { RefreshCw, Activity } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Badge } from '@/components/common/Badge'

interface CommandCenterHeaderProps {
  timeWindow: '1h' | '24h' | '7d' | '30d' | 'all'
  onTimeWindowChange: (window: '1h' | '24h' | '7d' | '30d' | 'all') => void
  autoRefreshInterval: number // in seconds, 0 = off
  onAutoRefreshChange: (interval: number) => void
  isLoading: boolean
  onRefresh: () => void
  systemStatus: string
}

const TIME_WINDOWS: Array<'1h' | '24h' | '7d' | '30d' | 'all'> = ['1h', '24h', '7d', '30d', 'all']
const AUTO_REFRESH_OPTIONS = [
  { label: 'Off', value: 0 },
  { label: '10s', value: 10 },
  { label: '30s', value: 30 },
  { label: '60s', value: 60 },
]

export const CommandCenterHeader: React.FC<CommandCenterHeaderProps> = ({
  timeWindow,
  onTimeWindowChange,
  autoRefreshInterval,
  onAutoRefreshChange,
  isLoading,
  onRefresh,
  systemStatus,
}) => {
  const isHealthy = systemStatus === 'OPERATIONAL'
  const isDegraded = systemStatus === 'DEGRADED'

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-border/40">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground font-sans">
            Veritas RAG <span className="text-primary font-medium text-lg sm:text-xl">Command Center</span>
          </h1>
          <Badge
            variant={isHealthy ? 'success' : isDegraded ? 'warning' : 'destructive'}
            className="flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-semibold"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isHealthy ? 'bg-emerald-500 animate-pulse' : isDegraded ? 'bg-amber-500' : 'bg-rose-500'
              }`}
            />
            {systemStatus}
          </Badge>
        </div>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1 max-w-2xl">
          Autonomous self-correcting RAG observability, latency decomposition, and execution flight recorder.
        </p>
      </div>

      <div className="flex items-center gap-2.5 flex-wrap">
        {/* Time Window Switcher */}
        <div className="flex items-center bg-card/60 backdrop-blur-sm p-1 rounded-lg border border-border/60 text-xs shadow-sm">
          {TIME_WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => onTimeWindowChange(w)}
              className={`px-3 py-1 rounded-md font-medium text-xs transition-all ${
                timeWindow === w
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {w.toUpperCase()}
            </button>
          ))}
        </div>

        {/* Auto-Refresh Toggle */}
        <div className="flex items-center bg-card/60 backdrop-blur-sm px-2.5 py-1 rounded-lg border border-border/60 text-xs gap-1.5 text-muted-foreground">
          <Activity className="h-3 w-3 text-muted-foreground/80" />
          <span className="hidden sm:inline text-[11px] font-medium">Auto-refresh:</span>
          <select
            value={autoRefreshInterval}
            onChange={(e) => onAutoRefreshChange(Number(e.target.value))}
            className="bg-transparent text-foreground text-xs font-medium focus:outline-none cursor-pointer"
            aria-label="Auto refresh interval"
          >
            {AUTO_REFRESH_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-popover text-popover-foreground">
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Manual Refresh Button */}
        <Button
          onClick={onRefresh}
          isLoading={isLoading}
          variant="secondary"
          size="sm"
          className="shrink-0 shadow-sm"
        >
          {!isLoading && <RefreshCw className="h-3.5 w-3.5 mr-1.5" />}
          Refresh
        </Button>
      </div>
    </div>
  )
}
