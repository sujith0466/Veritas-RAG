import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  RefreshCw,
  Layers,
  Cpu,
  Database,
  FileText,
  CheckCircle2,
  ShieldCheck,
  Clock,
} from 'lucide-react'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { Card, MotionCard, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
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
import { ReportExportDialog } from '@/components/analytics/ReportExportDialog'
import { dashboardService } from '@/services/dashboardService'
import type { KnowledgeIntelligenceSummaryDTO } from '@/types'
import { listContainerVariants, listItemVariants, cardHover } from '@/motion'

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
      setError('Unable to fetch knowledge intelligence metrics. Please verify your connection.')
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <PageHeader
          title="Knowledge Intelligence Dashboard"
          description="Autonomous observability across document ingestion, semantic chunking, embedding token budgets, and Qdrant vector cluster health."
        />

        <div className="flex items-center gap-3 shrink-0">
          <Button
            onClick={loadData}
            isLoading={isLoading}
            variant="secondary"
            size="sm"
          >
            {!isLoading && <RefreshCw className="mr-2 h-3.5 w-3.5" />}
            Refresh Intelligence
          </Button>

          <Button
            onClick={() => setIsExportOpen(true)}
            variant="outline"
            size="sm"
            className="text-primary hover:text-primary hover:bg-primary-subtle border-primary-subtle"
          >
            <FileText className="mr-2 h-3.5 w-3.5" />
            Export Health Audit
          </Button>
        </div>
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
          {/* Top Overview Cards */}
          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8"
          >
            <MotionCard variants={listItemVariants} whileHover={cardHover} className="shadow-card hover:shadow-card-hover transition-shadow duration-300">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Documents & Pass Rate
                </CardTitle>
                <div className="p-2 rounded-lg bg-primary-subtle text-primary">
                  <FileText className="h-4 w-4" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold tracking-tight text-foreground">
                  {isLoading ? '...' : data?.total_documents ?? 0}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-success font-medium mt-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>{data?.validation_pass_rate.toFixed(1)}% Validation SLA</span>
                </div>
              </CardContent>
            </MotionCard>

            <MotionCard variants={listItemVariants} whileHover={cardHover} className="shadow-card hover:shadow-card-hover transition-shadow duration-300">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Knowledge Chunks
                </CardTitle>
                <div className="p-2 rounded-lg bg-warning-subtle text-warning">
                  <Layers className="h-4 w-4" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold tracking-tight text-foreground">
                  {isLoading ? '...' : totalChunks}
                </div>
                <div className="text-xs text-muted-foreground mt-1 font-medium">
                  Avg <span className="font-semibold text-foreground">{data?.avg_tokens_per_chunk.toFixed(1)}</span> tokens/chunk
                </div>
              </CardContent>
            </MotionCard>

            <MotionCard variants={listItemVariants} whileHover={cardHover} className="shadow-card hover:shadow-card-hover transition-shadow duration-300">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Vector Embeddings
                </CardTitle>
                <div className="p-2 rounded-lg bg-info-subtle text-info">
                  <Cpu className="h-4 w-4" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold tracking-tight text-foreground">
                  {isLoading ? '...' : totalEmbeddings}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1 truncate">
                  <span className="font-semibold text-foreground">{data?.active_embedding_provider}</span>
                  <span>({data?.active_embedding_model})</span>
                </div>
              </CardContent>
            </MotionCard>

            <MotionCard variants={listItemVariants} whileHover={cardHover} className="shadow-card hover:shadow-card-hover transition-shadow duration-300">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Qdrant Cluster Parity
                </CardTitle>
                <div className="p-2 rounded-lg bg-success-subtle text-success">
                  <Database className="h-4 w-4" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={isParitySynced || data?.parity_audit_status === 'PARITY_CONFIRMED' ? 'success' : 'warning'}
                    className="text-xs px-2 py-0.5 font-bold tracking-wide"
                  >
                    {data?.parity_audit_status ?? 'SYNCING'}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground mt-2 flex items-center justify-between font-medium">
                  <span>Points: {data?.total_vector_points ?? 0}</span>
                  <span className="text-success uppercase">{data?.vector_cluster_status ?? 'green'} cluster</span>
                </div>
              </CardContent>
            </MotionCard>
          </motion.div>

          {/* Middle Grid: Chunk Strategies & Stage Latencies */}
          <motion.div
            variants={listContainerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8"
          >
            {/* Strategy Breakdown Card */}
            <MotionCard variants={listItemVariants} className="lg:col-span-6 shadow-card flex flex-col">
              <CardHeader className="border-b border-border/40 pb-4 shrink-0">
                <CardTitle className="flex items-center justify-between">
                  <span className="text-base font-bold">Semantic Strategy Distribution</span>
                  <Badge variant="outline" className="text-[11px] font-medium tracking-wide">Token Quota Tracked</Badge>
                </CardTitle>
                <CardDescription>
                  Breakdown of chunk generation across fixed-token, semantic boundary, and hierarchical strategies.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-6 flex-1 flex flex-col justify-between">
                {isLoading ? (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm min-h-[160px]">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Loading strategy breakdown...
                  </div>
                ) : Object.keys(data?.chunk_strategy_counts ?? {}).length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center min-h-[160px]">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-3">
                      <Layers className="h-6 w-6 text-muted-foreground/50" />
                    </div>
                    <p className="text-sm font-medium text-foreground">No Chunking Data Available</p>
                    <p className="text-xs text-muted-foreground mt-1">Ingest documents to generate semantic clusters.</p>
                  </div>
                ) : (
                  <div className="space-y-5 flex-1">
                    {Object.entries(data?.chunk_strategy_counts ?? {}).map(([strategy, count], index) => {
                      const percentage = totalChunks > 0 ? (count / totalChunks) * 100 : 0
                      const colors = ['bg-primary', 'bg-success', 'bg-warning', 'bg-info']
                      const barColor = colors[index % colors.length]

                      return (
                        <div key={strategy} className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-semibold capitalize text-foreground">{strategy} Strategy</span>
                            <span className="text-muted-foreground text-xs">
                              <span className="font-bold text-foreground">{count}</span> chunks ({percentage.toFixed(1)}%)
                            </span>
                          </div>
                          <div className="h-2 w-full bg-border/50 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${percentage}%` }}
                              transition={{ duration: 1, ease: 'easeOut' }}
                              className={`h-full ${barColor}`}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}

                <div className="mt-6 pt-4 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground shrink-0">
                  <span className="font-medium">Total API Tokens Consumed</span>
                  <span className="font-mono font-bold text-foreground bg-muted px-2 py-1 rounded">
                    {(data?.total_embedding_tokens_consumed ?? 0).toLocaleString()} tokens
                  </span>
                </div>
              </CardContent>
            </MotionCard>

            {/* Pipeline Stage Benchmarks */}
            <MotionCard variants={listItemVariants} className="lg:col-span-6 shadow-card flex flex-col">
              <CardHeader className="border-b border-border/40 pb-4 shrink-0">
                <CardTitle className="flex items-center justify-between">
                  <span className="text-base font-bold">Pipeline Stage Latencies (P50 Avg)</span>
                  <div className="h-6 w-6 rounded bg-muted flex items-center justify-center">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                </CardTitle>
                <CardDescription>
                  Processing performance across validation, extraction, chunking, and Qdrant storage.
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-6 flex-1 flex flex-col">
                {isLoading ? (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm min-h-[160px]">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Loading stage benchmarks...
                  </div>
                ) : (
                  <div className="space-y-5 flex-1">
                    {(data?.stage_latencies ?? []).map((stage, i) => {
                      const maxDuration = Math.max(
                        ...(data?.stage_latencies.map((s) => s.avg_duration_ms) ?? [250]),
                        250
                      )
                      const percentage = Math.min((stage.avg_duration_ms / maxDuration) * 100, 100)

                      return (
                        <div key={stage.stage_name} className="space-y-2">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-medium text-foreground">{stage.stage_name}</span>
                            <span className="font-mono font-semibold text-primary text-xs">
                              {stage.avg_duration_ms.toFixed(1)} ms
                            </span>
                          </div>
                          <div className="h-1.5 w-full bg-border/50 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${percentage}%` }}
                              transition={{ duration: 1, ease: 'easeOut', delay: i * 0.1 }}
                              className="h-full bg-primary/80"
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </CardContent>
            </MotionCard>
          </motion.div>

          {/* Recent Cluster Health Scans */}
          <motion.div variants={listItemVariants} initial="hidden" animate="visible">
            <Card className="shadow-card">
              <CardHeader className="border-b border-border/40 pb-4">
                <CardTitle className="flex items-center justify-between">
                  <span className="text-base font-bold">Recent Cluster Health & Parity Audits</span>
                  <div className="h-6 w-6 rounded bg-success-subtle flex items-center justify-center">
                    <ShieldCheck className="h-3.5 w-3.5 text-success" />
                  </div>
                </CardTitle>
                <CardDescription>
                  Autonomous background sweep history verifying orphan cleanup and vector synchronization.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                {isLoading ? (
                  <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
                    <RefreshCw className="h-5 w-5 animate-spin mr-2" />
                    Loading recent health scans...
                  </div>
                ) : (data?.recent_health_scans ?? []).length === 0 ? (
                  <div className="py-12 text-center text-muted-foreground text-sm">
                    No recent background health scans recorded yet.
                  </div>
                ) : (
                  <div className="overflow-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="hover:bg-transparent">
                          <TableHead>Scan Job ID</TableHead>
                          <TableHead>Scan Type</TableHead>
                          <TableHead>Parity Status</TableHead>
                          <TableHead>Orphans Found</TableHead>
                          <TableHead>Orphans Purged</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Timestamp</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(data?.recent_health_scans ?? []).map((scan) => (
                          <TableRow key={scan.id}>
                            <TableCell className="font-mono text-xs text-muted-foreground max-w-[120px] truncate">
                              {scan.id}
                            </TableCell>
                            <TableCell className="font-semibold">
                              {scan.scan_type}
                            </TableCell>
                            <TableCell>
                              <Badge variant="subtle" className="text-[10px] uppercase font-bold tracking-wide">
                                {scan.parity_status || 'UNKNOWN'}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono font-medium">{scan.orphans_found ?? 0}</TableCell>
                            <TableCell className="font-mono text-success font-semibold">{scan.orphans_purged ?? 0}</TableCell>
                            <TableCell>
                              <Badge
                                variant={scan.status === 'COMPLETED' ? 'success' : scan.status === 'FAILED' ? 'destructive' : 'warning'}
                                className="text-[10px]"
                              >
                                {scan.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-muted-foreground text-xs">
                              {scan.created_at ? new Date(scan.created_at).toLocaleString() : 'N/A'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </>
      )}
      <ReportExportDialog isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
    </PageTransition>
  )
}
