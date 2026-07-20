import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  RefreshCw,
  Layers,
  Cpu,
  Database,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Clock,
} from 'lucide-react'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { ReportExportDialog } from '@/components/analytics/ReportExportDialog'
import { dashboardService } from '@/services/dashboardService'
import type { KnowledgeIntelligenceSummaryDTO } from '@/types'

export function KnowledgeIntelligenceDashboardPage() {
  const [data, setData] = useState<KnowledgeIntelligenceSummaryDTO | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isExportOpen, setIsExportOpen] = useState(false)

  const loadData = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const summary = await dashboardService.getKnowledgeIntelligenceSummary()
      setData(summary)
    } catch (err) {
      console.error('Failed to load knowledge intelligence summary:', err)
      setError('Unable to fetch knowledge intelligence metrics.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const totalChunks = data?.total_chunks ?? 0
  const totalEmbeddings = data?.total_embeddings ?? 0
  const isParitySynced = totalChunks > 0 && totalChunks === totalEmbeddings

  return (
    <PageTransition>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <PageHeader
          title="Knowledge Intelligence Dashboard"
          description="Autonomous observability across document ingestion, semantic chunking, embedding token budgets, and Qdrant vector cluster health."
        />

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-all shadow-sm shrink-0"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Intelligence
          </button>

          <button
            onClick={() => setIsExportOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-primary/10 text-primary border border-primary/30 hover:bg-primary hover:text-primary-foreground transition-all shadow-sm shrink-0"
          >
            <FileText className="h-3.5 w-3.5" />
            Export Health Audit
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 mb-6 rounded-lg bg-danger/10 border border-danger/30 text-danger text-sm flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Top Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="bg-surface/80 border-border/60 shadow-sm relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Documents & Pass Rate
            </CardTitle>
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <FileText className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {isLoading ? '...' : data?.total_documents ?? 0}
            </div>
            <div className="flex items-center gap-1 text-xs text-emerald-500 font-medium mt-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{data?.validation_pass_rate.toFixed(1)}% Validation SLA</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-surface/80 border-border/60 shadow-sm relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Knowledge Chunks
            </CardTitle>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-500">
              <Layers className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {isLoading ? '...' : totalChunks}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              Avg <span className="font-semibold text-foreground">{data?.avg_tokens_per_chunk.toFixed(1)}</span> tokens/chunk
            </div>
          </CardContent>
        </Card>

        <Card className="bg-surface/80 border-border/60 shadow-sm relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Vector Embeddings
            </CardTitle>
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-500">
              <Cpu className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {isLoading ? '...' : totalEmbeddings}
            </div>
            <div className="flex items-center gap-1 text-xs text-muted-foreground mt-1 truncate">
              <span className="font-semibold text-foreground">{data?.active_embedding_provider}</span>
              <span>({data?.active_embedding_model})</span>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-surface/80 border-border/60 shadow-sm relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Qdrant Cluster Parity
            </CardTitle>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-500">
              <Database className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Badge
                variant={isParitySynced || data?.parity_audit_status === 'PARITY_CONFIRMED' ? 'success' : 'warning'}
                className="text-xs px-2 py-0.5 font-bold"
              >
                {data?.parity_audit_status ?? 'SYNCING'}
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground mt-1.5 flex items-center justify-between">
              <span>Points: {data?.total_vector_points ?? 0}</span>
              <span className="text-emerald-500 font-semibold uppercase">{data?.vector_cluster_status ?? 'green'} cluster</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Middle Grid: Chunk Strategies & Stage Latencies */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        {/* Strategy Breakdown Card */}
        <Card className="lg:col-span-6 bg-surface/80 border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="text-base font-bold">Semantic Strategy Distribution</span>
              <Badge variant="outline" className="text-[11px]">Token Quota Tracked</Badge>
            </CardTitle>
            <CardDescription>
              Breakdown of chunk generation across fixed-token, semantic boundary, and hierarchical strategies.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                Loading strategy breakdown...
              </div>
            ) : Object.keys(data?.chunk_strategy_counts ?? {}).length === 0 ? (
              <div className="h-48 flex flex-col items-center justify-center border border-dashed border-border/60 rounded-xl bg-surface/30 p-6 text-center">
                <Layers className="h-8 w-8 text-muted-foreground/50 mb-2" />
                <p className="text-sm font-medium text-foreground">No Chunking Data Available</p>
                <p className="text-xs text-muted-foreground mt-0.5">Ingest documents to generate semantic clusters.</p>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {Object.entries(data?.chunk_strategy_counts ?? {}).map(([strategy, count], index) => {
                  const percentage = totalChunks > 0 ? (count / totalChunks) * 100 : 0
                  const colors = ['bg-primary', 'bg-emerald-500', 'bg-amber-500', 'bg-blue-500']
                  const barColor = colors[index % colors.length]

                  return (
                    <div key={strategy} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold capitalize text-foreground">{strategy} Strategy</span>
                        <span className="text-muted-foreground">
                          <span className="font-bold text-foreground">{count}</span> chunks ({percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 w-full bg-border/40 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${percentage}%` }}
                          transition={{ duration: 0.8, ease: 'easeOut' }}
                          className={`h-full ${barColor}`}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="mt-6 pt-4 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
              <span>Total API Tokens Consumed</span>
              <span className="font-mono font-bold text-foreground">
                {(data?.total_embedding_tokens_consumed ?? 0).toLocaleString()} tokens
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Pipeline Stage Benchmarks */}
        <Card className="lg:col-span-6 bg-surface/80 border-border/60 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="text-base font-bold">Pipeline Stage Latencies (P50 Avg)</span>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardTitle>
            <CardDescription>
              Processing performance across validation, extraction, chunking, and Qdrant storage.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
                Loading stage benchmarks...
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {(data?.stage_latencies ?? []).map((stage) => {
                  const maxDuration = Math.max(
                    ...(data?.stage_latencies.map((s) => s.avg_duration_ms) ?? [250]),
                    250
                  )
                  const percentage = Math.min((stage.avg_duration_ms / maxDuration) * 100, 100)

                  return (
                    <div key={stage.stage_name} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-medium text-foreground">{stage.stage_name}</span>
                        <span className="font-mono font-semibold text-primary">
                          {stage.avg_duration_ms.toFixed(1)} ms
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-border/40 rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${percentage}%` }}
                          transition={{ duration: 0.8, ease: 'easeOut' }}
                          className="h-full bg-primary/80"
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Cluster Health Scans */}
      <Card className="bg-surface/80 border-border/60 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span className="text-base font-bold">Recent Cluster Health & Parity Audits</span>
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
          </CardTitle>
          <CardDescription>
            Autonomous background sweep history verifying orphan cleanup and vector synchronization.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
              Loading recent health scans...
            </div>
          ) : (data?.recent_health_scans ?? []).length === 0 ? (
            <div className="py-8 text-center text-muted-foreground text-sm border border-dashed border-border/60 rounded-xl bg-surface/30">
              No recent background health scans recorded yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-border/60 text-muted-foreground font-semibold">
                    <th className="py-2.5 px-3">Scan Job ID</th>
                    <th className="py-2.5 px-3">Scan Type</th>
                    <th className="py-2.5 px-3">Parity Status</th>
                    <th className="py-2.5 px-3">Orphans Found</th>
                    <th className="py-2.5 px-3">Orphans Purged</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {(data?.recent_health_scans ?? []).map((scan) => (
                    <tr key={scan.id} className="hover:bg-surface/60 transition-colors">
                      <td className="py-3 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-[120px]">
                        {scan.id}
                      </td>
                      <td className="py-3 px-3 font-semibold text-foreground">
                        {scan.scan_type}
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant="outline" className="text-[10px]">
                          {scan.parity_status || 'UNKNOWN'}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 font-mono text-foreground">{scan.orphans_found ?? 0}</td>
                      <td className="py-3 px-3 font-mono text-emerald-500 font-semibold">{scan.orphans_purged ?? 0}</td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={scan.status === 'COMPLETED' ? 'success' : scan.status === 'FAILED' ? 'destructive' : 'warning'}
                          className="text-[10px]"
                        >
                          {scan.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-right text-muted-foreground">
                        {scan.created_at ? new Date(scan.created_at).toLocaleString() : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <ReportExportDialog isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
    </PageTransition>
  )
}
