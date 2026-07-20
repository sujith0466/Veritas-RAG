import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  HardDrive,
  Layers,
  Play,
  RefreshCw,
  Trash2,
  Zap,
} from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/common'
import { useKnowledgeHealthStore } from '@/stores/knowledgeHealthStore'
import type { ScanType } from '@/types'

export function KnowledgeHealthPanel() {
  const {
    parityAudit,
    scanHistory,
    totalJobs,
    isScanning,
    isLoading,
    error,
    fetchParity,
    runScan,
    fetchScanHistory,
    rotateModel,
    purgeDocument,
    clearError,
  } = useKnowledgeHealthStore()

  const [targetProvider, setTargetProvider] = useState('openai')
  const [targetModel, setTargetModel] = useState('text-embedding-3-large')
  const [purgeDocId, setPurgeDocId] = useState('')
  const [purgeFeedback, setPurgeFeedback] = useState<string | null>(null)
  const [rotationFeedback, setRotationFeedback] = useState<string | null>(null)

  useEffect(() => {
    fetchParity()
    fetchScanHistory()
  }, [fetchParity, fetchScanHistory])

  const handleRunScan = async (type: ScanType) => {
    clearError()
    await runScan(type)
  }

  const handleRotate = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()
    setRotationFeedback(null)
    const result = await rotateModel(targetProvider, targetModel)
    if (result) {
      setRotationFeedback(
        `Migration job ${result.job_id.slice(0, 8)}... started for ${result.stale_chunks_enqueued} stale chunks to ${result.target_provider}/${result.target_model}.`,
      )
    }
  }

  const handlePurge = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!purgeDocId.trim()) return
    clearError()
    setPurgeFeedback(null)
    const summary = await purgeDocument(purgeDocId.trim())
    if (summary) {
      const qdrantCount = summary.qdrant_points_deleted ?? summary.purged_points_count ?? 0
      const pgCount = summary.pg_chunks_deleted ?? 0
      const duration = summary.duration_ms ?? 0
      setPurgeFeedback(
        `Purged ${qdrantCount} vector points and ${pgCount} DB chunks for document ${summary.document_id.slice(0, 8)}... (${duration.toFixed(1)}ms).`,
      )
      setPurgeDocId('')
    }
  }

  return (
    <div className="space-y-8">
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger dark:bg-danger/20"
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 flex-shrink-0" />
            <span><strong>System Notice:</strong> {error}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={clearError}>
            Dismiss
          </Button>
        </motion.div>
      )}

      {/* ── 1. Real-time Count Parity Banner (`ADR-M6-001`) ───────────────── */}
      <Card className="border-2 border-primary/20 bg-gradient-to-br from-card to-primary/5 shadow-md">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-xl font-bold">
              <Database className="h-6 w-6 text-primary" />
              Real-Time 1:1 Parity Audit
            </CardTitle>
            <CardDescription>
              Compares active PostgreSQL chunk records against indexed Qdrant vector points (`ADR-M6-001`).
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchParity()}
            disabled={isLoading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Verify Now
          </Button>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid gap-6 sm:grid-cols-3">
            <div className="rounded-lg border bg-card/60 p-4 shadow-sm backdrop-blur-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                PostgreSQL Chunks
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold tracking-tight">
                  {parityAudit ? parityAudit.pg_chunk_count.toLocaleString() : '—'}
                </span>
                <span className="text-xs text-muted-foreground">active records</span>
              </div>
            </div>

            <div className="rounded-lg border bg-card/60 p-4 shadow-sm backdrop-blur-sm">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Qdrant Vector Points
              </span>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-3xl font-extrabold tracking-tight">
                  {parityAudit ? parityAudit.qdrant_point_count.toLocaleString() : '—'}
                </span>
                <span className="text-xs text-muted-foreground">indexed vectors</span>
              </div>
            </div>

            <div className="rounded-lg border bg-card/60 p-4 shadow-sm backdrop-blur-sm flex flex-col justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Parity Status
              </span>
              <div className="mt-2 flex items-center gap-2">
                {parityAudit ? (
                  parityAudit.is_synced ? (
                    <Badge variant="success" className="gap-1.5 py-1 px-3 text-sm font-semibold shadow-sm">
                      <CheckCircle2 className="h-4 w-4" />
                      SYNCED (1:1 PARITY)
                    </Badge>
                  ) : (
                    <Badge variant="destructive" className="gap-1.5 py-1 px-3 text-sm font-semibold shadow-sm">
                      <AlertTriangle className="h-4 w-4" />
                      DRIFT MISMATCH DETECTED
                    </Badge>
                  )
                ) : (
                  <Badge variant="secondary">Not Checked</Badge>
                )}
              </div>
              <span className="text-[11px] text-muted-foreground">
                Last checked: {parityAudit ? new Date(parityAudit.checked_at).toLocaleTimeString() : 'N/A'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── 2. Maintenance Scan Engine Actions ───────────────────────────── */}
      <div>
        <h3 className="mb-4 text-lg font-bold flex items-center gap-2 text-foreground">
          <Zap className="h-5 w-5 text-warning" />
          Autonomous Maintenance & Lifecycle Sweeps
        </h3>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <Card className="hover:border-primary/50 transition-all shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Trash2 className="h-4 w-4 text-danger" />
                Orphan Cleanup Sweep
              </CardTitle>
              <CardDescription className="text-xs">
                Purges orphaned vector points whose parent documents or versions were deleted.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                className="w-full justify-between font-medium"
                disabled={isScanning}
                onClick={() => handleRunScan('ORPHAN_SWEEP')}
              >
                Run Orphan Sweep
                <Play className="h-3.5 w-3.5 fill-current" />
              </Button>
            </CardContent>
          </Card>

          <Card className="hover:border-primary/50 transition-all shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                Parity Audit Sweep
              </CardTitle>
              <CardDescription className="text-xs">
                Scans all collections to verify count parity and flags discrepancies.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                className="w-full justify-between font-medium"
                disabled={isScanning}
                onClick={() => handleRunScan('PARITY_AUDIT')}
              >
                Run Parity Audit
                <Play className="h-3.5 w-3.5 fill-current" />
              </Button>
            </CardContent>
          </Card>

          <Card className="hover:border-primary/50 transition-all shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Layers className="h-4 w-4 text-purple-500" />
                Model Rotation Scan
              </CardTitle>
              <CardDescription className="text-xs">
                Detects chunks vectorized with deprecated models or providers (`ADR-M6-002`).
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                className="w-full justify-between font-medium"
                disabled={isScanning}
                onClick={() => handleRunScan('MODEL_ROTATION_SCAN')}
              >
                Run Rotation Scan
                <Play className="h-3.5 w-3.5 fill-current" />
              </Button>
            </CardContent>
          </Card>

          <Card className="border-primary/40 bg-primary/5 hover:border-primary transition-all shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2 text-primary">
                <Zap className="h-4 w-4" />
                Full Lifecycle Sweep
              </CardTitle>
              <CardDescription className="text-xs">
                Sequentially runs all orphan sweeps, parity audits, and rotation detections.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="default"
                className="w-full justify-between font-semibold shadow-md"
                disabled={isScanning}
                onClick={() => handleRunScan('ALL')}
              >
                {isScanning ? 'Scanning...' : 'Run All Sweeps'}
                <Play className="h-3.5 w-3.5 fill-current" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* ── 3. Model Rotation & Explicit Purge Tools ─────────────────────── */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Layers className="h-5 w-5 text-purple-500" />
              Zero-Downtime Model Rotation (`ADR-M6-002`)
            </CardTitle>
            <CardDescription>
              Initiate shadow re-indexing of tenant chunks to a new embedding provider and dimension without interrupting active queries.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRotate} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="provider">Target Provider</Label>
                  <Select
                    value={targetProvider}
                    onValueChange={(val) => setTargetProvider(val)}
                  >
                    <SelectTrigger id="provider">
                      <SelectValue placeholder="Select provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="cohere">Cohere</SelectItem>
                      <SelectItem value="gemini">Google Gemini</SelectItem>
                      <SelectItem value="local">Local HuggingFace</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="model">Target Model</Label>
                  <Input
                    id="model"
                    value={targetModel}
                    onChange={(e) => setTargetModel(e.target.value)}
                    placeholder="e.g. text-embedding-3-large"
                    required
                  />
                </div>
              </div>

              {rotationFeedback && (
                <div className="rounded-md bg-success/10 p-3 text-xs text-success border border-success/30 font-medium">
                  {rotationFeedback}
                </div>
              )}

              <Button type="submit" variant="outline" className="w-full font-semibold" disabled={isLoading}>
                Start Shadow Re-Indexing Campaign
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <HardDrive className="h-5 w-5 text-danger" />
              Two-Phase Document Purge (`ADR-M6-001`)
            </CardTitle>
            <CardDescription>
              Atomically delete document vectors from Qdrant (`Phase 1`) and cascade hard deletion across DB versions (`Phase 2`).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePurge} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="docUuid">Document UUID</Label>
                <Input
                  id="docUuid"
                  value={purgeDocId}
                  onChange={(e) => setPurgeDocId(e.target.value)}
                  placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                  required
                />
              </div>

              {purgeFeedback && (
                <div className="rounded-md bg-primary/10 p-3 text-xs text-primary border border-primary/30 font-medium">
                  {purgeFeedback}
                </div>
              )}

              <Button type="submit" variant="destructive" className="w-full font-semibold shadow-sm" disabled={isLoading || !purgeDocId.trim()}>
                Execute Two-Phase Hard Purge
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* ── 4. Scan Job History Table ───────────────────────────────────── */}
      <Card className="shadow-sm">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg font-bold">Lifecycle Audit History</CardTitle>
            <CardDescription>
              Recent autonomous sweeps and parity checks ({totalJobs} total records).
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={() => fetchScanHistory()} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-1.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </CardHeader>
        <CardContent>
          {scanHistory.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground border-2 border-dashed rounded-md">
              No health scan jobs recorded yet. Click one of the autonomous sweep buttons above to initiate your first audit!
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="py-3 px-4 font-semibold">Job ID</th>
                    <th className="py-3 px-4 font-semibold">Scan Type</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold text-right">Orphans Purged</th>
                    <th className="py-3 px-4 font-semibold">Parity Result</th>
                    <th className="py-3 px-4 font-semibold text-right">Duration</th>
                    <th className="py-3 px-4 font-semibold text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {scanHistory.map((job) => (
                    <tr key={job.id} className="hover:bg-muted/30 transition-colors">
                      <td className="py-3 px-4 font-mono text-xs text-muted-foreground">
                        {job.id.slice(0, 8)}...
                      </td>
                      <td className="py-3 px-4 font-semibold">
                        <Badge variant="subtle" className="font-mono text-[11px]">
                          {job.scan_type}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={
                            job.status === 'COMPLETED'
                              ? 'success'
                              : job.status === 'FAILED'
                                ? 'destructive'
                                : 'warning'
                          }
                          className="text-[11px]"
                        >
                          {job.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 text-right font-medium">
                        {job.orphans_purged}
                      </td>
                      <td className="py-3 px-4 text-xs font-mono">
                        <span className={job.parity_status.includes('SYNCED') ? 'text-success font-semibold' : 'text-danger font-semibold'}>
                          {job.parity_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right text-xs font-mono text-muted-foreground">
                        {job.duration_ms ? `${job.duration_ms.toFixed(1)}ms` : '—'}
                      </td>
                      <td className="py-3 px-4 text-right text-xs text-muted-foreground">
                        {new Date(job.created_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
