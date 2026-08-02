import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { MotionCard, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { ErrorState } from '@/components/common/ErrorState'
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/common/Table'
import { Shield, Activity, Users, FileText, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { dashboardService } from '@/services/dashboardService'
import type { ExecutiveDashboardDTO } from '@/types'
import { listContainerVariants, listItemVariants, cardHover } from '@/motion'

export function DashboardPage() {
  const [data, setData] = useState<ExecutiveDashboardDTO | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const execSummary = await dashboardService.getExecutiveDashboard()
      setData(execSummary)
    } catch (err) {
      console.error('Failed to load executive dashboard summary:', err)
      setError('Unable to fetch executive dashboard metrics. Please check your connection and try again.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const stats = [
    {
      title: 'Active Tenants',
      value: isLoading ? '...' : String(data?.active_tenants ?? 1),
      icon: Users,
      trend: 'Isolated multi-tenant execution',
      color: 'text-info bg-info-subtle',
    },
    {
      title: 'Total Queries (24h)',
      value: isLoading ? '...' : (data?.total_queries_last_24h ?? 0).toLocaleString(),
      icon: FileText,
      trend: `Avg Confidence: ${((data?.avg_confidence_score ?? 0.88) * 100).toFixed(1)}%`,
      color: 'text-primary bg-primary-subtle',
    },
    {
      title: 'Reliability Score',
      value: isLoading ? '...' : `${(data?.avg_reliability_score ?? 95.4).toFixed(1)}%`,
      icon: Activity,
      trend: `Clarification rate: ${(data?.clarification_rate ?? 0.0).toFixed(1)}%`,
      color: 'text-success bg-success-subtle',
    },
    {
      title: 'Blocked Hallucinations',
      value: isLoading ? '...' : String(data?.blocked_hallucinations_last_24h ?? 0),
      icon: Shield,
      trend: 'Safety threshold interventions',
      color: 'text-danger bg-danger-subtle',
    },
  ]

  return (
    <PageTransition>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <PageHeader
          title="Executive Overview"
          description="Autonomous AI observability, query reliability scoring, and hallucination prevention activity."
        />

        <Button
          onClick={loadData}
          isLoading={isLoading}
          variant="secondary"
          size="sm"
          className="shrink-0"
        >
          {!isLoading && <RefreshCw className="h-3.5 w-3.5 mr-2" />}
          Refresh Metrics
        </Button>
      </div>

      {error ? (
        <div className="mb-8">
          <ErrorState
            title="Dashboard Error"
            error={new Error(error)}
            onRetry={loadData}
          />
        </div>
      ) : (
        <>
          {/* KPI Stats Grid */}
          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8"
          >
            {stats.map((stat) => (
              <MotionCard
                key={stat.title}
                variants={listItemVariants}
                whileHover={cardHover}
                className="relative overflow-hidden group shadow-card hover:shadow-card-hover transition-shadow duration-300"
              >
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {stat.title}
                  </CardTitle>
                  <div className={`p-2 rounded-lg transition-transform duration-300 group-hover:scale-110 ${stat.color}`}>
                    <stat.icon className="h-4 w-4" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold tracking-tight text-foreground">{stat.value}</div>
                  <p className="text-xs text-muted-foreground mt-1 font-medium">
                    {stat.trend}
                  </p>
                </CardContent>
              </MotionCard>
            ))}
          </motion.div>

          {/* Activity and Alerts Section */}
          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid gap-6 md:grid-cols-2 lg:grid-cols-12"
          >
            {/* Recent Query Activity Table */}
            <MotionCard variants={listItemVariants} className="lg:col-span-7 shadow-card flex flex-col">
              <CardHeader className="shrink-0">
                <CardTitle className="text-base font-bold flex items-center justify-between">
                  <span>Recent AI Execution Activity</span>
                  <Badge variant="subtle" className="text-[10px] animate-pulse-subtle">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary mr-1.5 inline-block"></span>
                    Live Stream
                  </Badge>
                </CardTitle>
                <CardDescription>
                  Real-time query execution history with pre-generation confidence and reliability scores.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 p-0 overflow-hidden flex flex-col">
                {isLoading ? (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm min-h-[250px]">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Loading query activity...
                  </div>
                ) : (data?.recent_activity ?? []).length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-8 text-center min-h-[250px]">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-3">
                      <FileText className="h-6 w-6 text-muted-foreground/60" />
                    </div>
                    <p className="text-sm font-medium text-foreground">No Query Execution Records Yet</p>
                    <p className="text-xs text-muted-foreground mt-1">Execute queries to view live evaluation dynamics.</p>
                  </div>
                ) : (
                  <div className="overflow-auto flex-1">
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead className="w-[40%]">Query Snippet</TableHead>
                          <TableHead>Outcome</TableHead>
                          <TableHead>Confidence</TableHead>
                          <TableHead>Latency</TableHead>
                          <TableHead className="text-right">Time</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(data?.recent_activity ?? []).map((item) => (
                          <TableRow key={item.id}>
                            <TableCell className="font-medium max-w-[200px] truncate" title={item.description}>
                              {item.description}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={item.status === 'SUCCESS' ? 'success' : item.status.includes('ABORTED') ? 'destructive' : 'warning'}
                                className="text-[10px]"
                              >
                                {item.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono text-xs">
                              {item.confidence_score !== null ? `${(item.confidence_score * 100).toFixed(0)}%` : 'N/A'}
                            </TableCell>
                            <TableCell className="font-mono text-xs text-muted-foreground">
                              {item.duration_ms !== null ? `${item.duration_ms.toFixed(0)}ms` : 'N/A'}
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground text-xs">
                              {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </MotionCard>

            {/* Security Alerts and Hallucination Interventions */}
            <MotionCard variants={listItemVariants} className="lg:col-span-5 shadow-card flex flex-col">
              <CardHeader className="shrink-0 border-b border-border/40 pb-4">
                <CardTitle className="text-base font-bold flex items-center justify-between">
                  <span>Security & Safety Interventions</span>
                  <div className="h-6 w-6 rounded bg-danger-subtle flex items-center justify-center">
                    <Shield className="h-3.5 w-3.5 text-danger" />
                  </div>
                </CardTitle>
                <CardDescription>
                  Autonomous context interventions, safety thresholds, and hallucination aborts.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 p-0 overflow-hidden flex flex-col">
                {isLoading ? (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm min-h-[250px]">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Loading safety alerts...
                  </div>
                ) : (data?.security_alerts ?? []).length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-8 text-center min-h-[250px]">
                    <div className="h-12 w-12 rounded-full bg-success-subtle flex items-center justify-center mb-3">
                      <CheckCircle2 className="h-6 w-6 text-success" />
                    </div>
                    <p className="text-sm font-medium text-foreground">Zero Safety Interventions Required</p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-[200px] mx-auto">All recent queries met strict pre-generation confidence criteria.</p>
                  </div>
                ) : (
                  <div className="overflow-y-auto flex-1 p-4 space-y-4">
                    {(data?.security_alerts ?? []).map((alert) => (
                      <div key={alert.id} className="group flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-muted/50 border border-transparent hover:border-border/50">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-lg shrink-0 ${
                          alert.severity === 'HIGH' ? 'bg-danger-subtle text-danger' : 'bg-warning-subtle text-warning'
                        }`}>
                          <AlertTriangle className="h-4 w-4" />
                        </div>
                        <div className="flex-1 space-y-1.5 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-bold tracking-tight text-foreground truncate pr-2">
                              {alert.alert_type}
                            </p>
                            <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                              {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="bg-background rounded px-2 py-1.5 border border-border/40">
                            <p className="text-[11px] font-medium text-foreground/90 italic truncate" title={alert.query_snippet}>
                              &quot;{alert.query_snippet}&quot;
                            </p>
                          </div>
                          <p className="text-[11px] text-muted-foreground leading-snug">
                            {alert.reason}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </MotionCard>
          </motion.div>
        </>
      )}
    </PageTransition>
  )
}
