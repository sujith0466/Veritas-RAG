import { useState, useEffect, useCallback } from 'react'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Shield, Activity, Users, FileText, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { dashboardService } from '@/services/dashboardService'
import type { ExecutiveDashboardDTO } from '@/types'

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
      setError('Unable to fetch executive dashboard metrics.')
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
      color: 'text-blue-500 bg-blue-500/10',
    },
    {
      title: 'Total Queries (24h)',
      value: isLoading ? '...' : (data?.total_queries_last_24h ?? 0).toLocaleString(),
      icon: FileText,
      trend: `Avg Confidence: ${((data?.avg_confidence_score ?? 0.88) * 100).toFixed(1)}%`,
      color: 'text-primary bg-primary/10',
    },
    {
      title: 'Reliability Score',
      value: isLoading ? '...' : `${(data?.avg_reliability_score ?? 95.4).toFixed(1)}%`,
      icon: Activity,
      trend: `Clarification rate: ${(data?.clarification_rate ?? 0.0).toFixed(1)}%`,
      color: 'text-emerald-500 bg-emerald-500/10',
    },
    {
      title: 'Blocked Hallucinations',
      value: isLoading ? '...' : String(data?.blocked_hallucinations_last_24h ?? 0),
      icon: Shield,
      trend: 'Safety threshold interventions',
      color: 'text-danger bg-danger/10',
    },
  ]

  return (
    <PageTransition>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <PageHeader 
          title="Executive Overview" 
          description="Autonomous AI observability, query reliability scoring, and hallucination prevention activity."
        />

        <button
          onClick={loadData}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all shadow-sm shrink-0"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh Metrics
        </button>
      </div>

      {error && (
        <div className="p-4 mb-6 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* KPI Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.title} className="bg-surface/80 border-border/60 shadow-sm relative overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {stat.title}
              </CardTitle>
              <div className={`p-2 rounded-lg ${stat.color}`}>
                <stat.icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold tracking-tight text-foreground">{stat.value}</div>
              <p className="text-xs text-muted-foreground mt-1 font-medium">
                {stat.trend}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Activity and Alerts Section */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-12">
        {/* Recent Query Activity Table */}
        <Card className="lg:col-span-7 bg-surface/80 border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center justify-between">
              <span>Recent AI Execution Activity</span>
              <Badge variant="outline" className="text-[11px]">Live Stream</Badge>
            </CardTitle>
            <CardDescription>
              Real-time query execution history with pre-generation confidence and reliability scores.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
                Loading query activity...
              </div>
            ) : (data?.recent_activity ?? []).length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center border border-dashed border-border/60 rounded-xl bg-surface/30 p-6 text-center">
                <FileText className="h-8 w-8 text-muted-foreground/50 mb-2" />
                <p className="text-sm font-medium text-foreground">No Query Execution Records Yet</p>
                <p className="text-xs text-muted-foreground mt-0.5">Execute queries to view live evaluation dynamics.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border/60 text-muted-foreground font-semibold">
                      <th className="py-2 px-2">Query Snippet</th>
                      <th className="py-2 px-2">Outcome</th>
                      <th className="py-2 px-2">Confidence</th>
                      <th className="py-2 px-2">Latency</th>
                      <th className="py-2 px-2 text-right">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {(data?.recent_activity ?? []).map((item) => (
                      <tr key={item.id} className="hover:bg-surface/60 transition-colors">
                        <td className="py-2.5 px-2 font-medium text-foreground max-w-[200px] truncate">
                          {item.description}
                        </td>
                        <td className="py-2.5 px-2">
                          <Badge
                            variant={item.status === 'SUCCESS' ? 'success' : item.status.includes('ABORTED') ? 'destructive' : 'warning'}
                            className="text-[10px]"
                          >
                            {item.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-2 font-mono">
                          {item.confidence_score !== null ? `${(item.confidence_score * 100).toFixed(0)}%` : 'N/A'}
                        </td>
                        <td className="py-2.5 px-2 font-mono text-muted-foreground">
                          {item.duration_ms !== null ? `${item.duration_ms.toFixed(0)}ms` : 'N/A'}
                        </td>
                        <td className="py-2.5 px-2 text-right text-muted-foreground">
                          {new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Security Alerts and Hallucination Interventions */}
        <Card className="lg:col-span-5 bg-surface/80 border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle className="text-base font-bold flex items-center justify-between">
              <span>Security & Safety Interventions</span>
              <Shield className="h-4 w-4 text-danger" />
            </CardTitle>
            <CardDescription>
              Autonomous context interventions, safety thresholds, and hallucination aborts.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground text-sm">
                Loading safety alerts...
              </div>
            ) : (data?.security_alerts ?? []).length === 0 ? (
              <div className="h-64 flex flex-col items-center justify-center border border-dashed border-border/60 rounded-xl bg-surface/30 p-6 text-center">
                <CheckCircle2 className="h-8 w-8 text-emerald-500/60 mb-2" />
                <p className="text-sm font-medium text-foreground">Zero Safety Interventions Required</p>
                <p className="text-xs text-muted-foreground mt-0.5">All recent queries met strict pre-generation confidence criteria.</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-[360px] overflow-y-auto pr-1">
                {(data?.security_alerts ?? []).map((alert) => (
                  <div key={alert.id} className="flex items-start gap-3 border-b border-border/40 pb-3.5 last:border-0 last:pb-0">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full shrink-0 mt-0.5 ${
                      alert.severity === 'HIGH' ? 'bg-danger/10 text-danger' : 'bg-warning/10 text-warning'
                    }`}>
                      <AlertTriangle className="h-4 w-4" />
                    </div>
                    <div className="flex-1 space-y-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-bold leading-none text-foreground truncate">
                          {alert.alert_type}
                        </p>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs font-medium text-foreground/90 italic truncate">
                        "{alert.query_snippet}"
                      </p>
                      <p className="text-[11px] text-muted-foreground leading-snug">
                        {alert.reason}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageTransition>
  )
}
