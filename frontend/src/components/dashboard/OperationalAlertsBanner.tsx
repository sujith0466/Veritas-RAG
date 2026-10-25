import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { dashboardCardHover } from '@/motion'
import { AlertTriangle, CheckCircle2, ShieldAlert } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import type { ExecutiveDashboardAlertDTO } from '@/types'

interface OperationalAlertsBannerProps {
  alerts: ExecutiveDashboardAlertDTO[]
  isLoading: boolean
}

export const OperationalAlertsBanner: React.FC<OperationalAlertsBannerProps> = ({
  alerts,
  isLoading,
}) => {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      whileHover={shouldReduceMotion ? undefined : dashboardCardHover}
      className="h-full"
    >
      <Card className="bg-card/70 backdrop-blur-md border border-border/70 hover:border-border/90 transition-colors duration-200 shadow-sm flex flex-col h-full">
        <CardHeader className="pb-3 border-b border-border/40">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-rose-400" />
                Safety & Autonomous Interventions
              </CardTitle>
              <CardDescription className="text-xs">
                Hallucination prevention aborts, policy blocks, and confidence corrections.
              </CardDescription>
            </div>
            <Badge
              variant={alerts.length > 0 ? 'warning' : 'subtle'}
              className="text-[11px] font-mono tabular-nums shrink-0"
            >
              {alerts.length} {alerts.length === 1 ? 'Incident' : 'Incidents'}
            </Badge>
          </div>
        </CardHeader>

        <CardContent className="p-0 overflow-hidden flex-1 flex flex-col min-h-[220px]">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center text-muted-foreground text-xs p-6">
              Loading safety interventions...
            </div>
          ) : alerts.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
              <motion.div
                initial={shouldReduceMotion ? false : { scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.3, ease: 'easeOut' }}
                className="h-10 w-10 rounded-full bg-emerald-500/10 flex items-center justify-center mb-2.5 text-emerald-400 border border-emerald-500/20"
              >
                <CheckCircle2 className="h-5 w-5" />
              </motion.div>
              <p className="text-sm font-semibold text-foreground">Zero Safety Interventions in Window</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-xs leading-relaxed">
                All processed queries in this time period satisfied strict grounding verification and confidence thresholds.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border/40 overflow-y-auto max-h-[300px]">
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="p-3.5 hover:bg-muted/40 transition-colors duration-150 flex items-start gap-3 text-xs"
                >
                  <div
                    className={`p-1.5 rounded-lg shrink-0 border ${
                      alert.severity === 'HIGH'
                        ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                    }`}
                  >
                    <AlertTriangle className="h-4 w-4" />
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-foreground truncate">{alert.alert_type}</span>
                      <span className="text-[11px] font-mono tabular-nums text-muted-foreground shrink-0">
                        {new Date(alert.timestamp).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>

                    <p className="text-[11px] text-muted-foreground/90 font-mono bg-background/50 px-2 py-1 rounded border border-border/40 truncate">
                      &quot;{alert.query_snippet}&quot;
                    </p>

                    <p className="text-[11px] text-muted-foreground leading-relaxed">{alert.reason}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
