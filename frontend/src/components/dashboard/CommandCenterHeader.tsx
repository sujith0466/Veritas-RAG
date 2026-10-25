import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { springs } from '@/motion'
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
  const shouldReduceMotion = useReducedMotion()
  const isHealthy = systemStatus === 'OPERATIONAL'
  const isDegraded = systemStatus === 'DEGRADED'

  return (
    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-border/40">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground font-sans">
            Veritas RAG <span className="text-primary font-medium text-lg sm:text-xl">Command Center</span>
          </h1>
          {!isHealthy && (
            <Badge
              variant={isDegraded ? 'warning' : 'destructive'}
              className="flex items-center gap-1.5 px-2.5 py-0.5 text-xs font-semibold"
              aria-label={systemStatus}
              title={systemStatus}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isDegraded ? 'bg-amber-500' : 'bg-rose-500'
                }`}
              />
              {systemStatus}
            </Badge>
          )}
        </div>
        <p className="text-xs sm:text-sm text-muted-foreground mt-1 max-w-2xl leading-relaxed">
          Autonomous self-correcting RAG observability, latency decomposition, and execution flight recorder.
        </p>
      </div>

      <div className="flex items-center gap-2.5 flex-wrap">
        {/* Time Window Switcher (Segmented Animated Pill Bar) */}
        <div
          role="radiogroup"
          aria-label="Select dashboard time window"
          className="flex items-center bg-surface/70 backdrop-blur-sm p-1 rounded-lg border border-border/60 text-xs shadow-xs"
        >
          {TIME_WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              role="radio"
              aria-checked={timeWindow === w}
              onClick={() => onTimeWindowChange(w)}
              className="relative px-3 py-1 rounded-md font-medium text-xs transition-colors duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
            >
              {timeWindow === w && (
                shouldReduceMotion ? (
                  <span className="absolute inset-0 bg-primary rounded-md shadow-xs z-0" />
                ) : (
                  <motion.span
                    layoutId="activeTimeWindowPill"
                    className="absolute inset-0 bg-primary rounded-md shadow-xs z-0"
                    transition={springs.snappy}
                  />
                )
              )}
              <span
                className={`relative z-10 transition-colors duration-150 ${
                  timeWindow === w
                    ? 'text-primary-foreground font-semibold'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {w.toUpperCase()}
              </span>
            </button>
          ))}
        </div>

        {/* Auto-Refresh Toggle */}
        <div className="flex items-center bg-surface/70 backdrop-blur-sm px-2.5 py-1 rounded-lg border border-border/60 text-xs gap-1.5 text-muted-foreground shadow-xs">
          <Activity className="h-3 w-3 text-muted-foreground/80" />
          <span className="hidden sm:inline text-[11px] font-medium">Auto-refresh:</span>
          <select
            value={autoRefreshInterval}
            onChange={(e) => onAutoRefreshChange(Number(e.target.value))}
            className="bg-transparent text-foreground text-xs font-medium focus:outline-none focus:ring-1 focus:ring-primary/50 rounded cursor-pointer pr-1 [color-scheme:light] dark:[color-scheme:dark]"
            aria-label="Auto refresh interval"
          >
            {AUTO_REFRESH_OPTIONS.map((opt) => (
              <option
                key={opt.value}
                value={opt.value}
                className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100 py-1"
              >
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
          className="group shrink-0 shadow-xs gap-1.5 hover:bg-muted transition-colors duration-150"
        >
          {!isLoading && (
            <RefreshCw className="h-3.5 w-3.5 group-hover:rotate-45 transition-transform duration-200" />
          )}
          Refresh
        </Button>
      </div>
    </div>
  )
}
