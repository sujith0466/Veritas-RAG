import { useState, useEffect } from 'react'
import {
  X,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Sliders,
  Layers,
  RefreshCw,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { analyticsService } from '@/services/analyticsService'
import { toPresentationPercentage } from '@/utils/telemetryAdapters'
import type {
  QueryTraceDetailDTO,
  StageTraceDTO,
  RetrievalCandidateTraceDTO,
  ConfidenceSignalTraceDTO,
  SelfCorrectionTraceDTO,
} from '@/types'

interface ForensicTraceDrawerProps {
  isOpen: boolean
  onClose: () => void
  correlationId?: string | null
  initialTrace?: QueryTraceDetailDTO | null
}

export function ForensicTraceDrawer({
  isOpen,
  onClose,
  correlationId,
  initialTrace = null,
}: ForensicTraceDrawerProps) {
  const [trace, setTrace] = useState<QueryTraceDetailDTO | null>(initialTrace)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedJson, setCopiedJson] = useState(false)
  const [activeTab, setActiveTab] = useState<'visual' | 'json'>('visual')

  useEffect(() => {
    if (initialTrace) {
      setTrace(initialTrace)
      return
    }

    if (isOpen && correlationId) {
      setIsLoading(true)
      setError(null)
      analyticsService
        .getQueryTraceDetail(correlationId)
        .then((data) => {
          setTrace(data)
        })
        .catch((err) => {
          console.error('Failed to load trace detail:', err)
          setError(err instanceof Error ? err.message : 'Failed to load trace detail')
        })
        .finally(() => {
          setIsLoading(false)
        })
    }
  }, [isOpen, correlationId, initialTrace])

  const handleCopyJson = () => {
    if (!trace) return
    navigator.clipboard.writeText(JSON.stringify(trace, null, 2))
    setCopiedJson(true)
    setTimeout(() => setCopiedJson(false), 2000)
  }

  const renderOutcomeBadge = (outcome: string) => {
    switch (outcome) {
      case 'SUCCESS':
        return (
          <Badge variant="success" className="flex items-center gap-1.5 uppercase font-bold tracking-wide">
            <CheckCircle2 className="h-3.5 w-3.5" /> SUCCESS
          </Badge>
        )
      case 'CLARIFICATION_REQUIRED':
        return (
          <Badge variant="warning" className="flex items-center gap-1.5 uppercase font-bold tracking-wide">
            <HelpCircle className="h-3.5 w-3.5" /> CLARIFICATION REQUIRED
          </Badge>
        )
      default:
        return (
          <Badge variant="destructive" className="flex items-center gap-1.5 uppercase font-bold tracking-wide">
            <XCircle className="h-3.5 w-3.5" /> {outcome}
          </Badge>
        )
    }
  }

  if (!isOpen) return null

  const isAuthoritative = trace?.is_authoritative !== false
  const totalDuration = trace?.record.total_duration_ms || 1

  const shouldReduceMotion = useReducedMotion()

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end">
        {/* Backdrop click to dismiss */}
        <div className="absolute inset-0" onClick={onClose} />

        <motion.div
          initial={shouldReduceMotion ? { opacity: 0 } : { x: '100%' }}
          animate={shouldReduceMotion ? { opacity: 1 } : { x: 0 }}
          exit={shouldReduceMotion ? { opacity: 0 } : { x: '100%' }}
          transition={
            shouldReduceMotion
              ? { duration: 0.15 }
              : { type: 'spring', damping: 25, stiffness: 220 }
          }
          className="relative z-10 w-full max-w-3xl bg-surface border-l border-border/80 shadow-2xl h-full flex flex-col overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border/60 bg-surface/80 flex items-center justify-between shrink-0">
            <div className="space-y-1 max-w-xl">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-primary" />
                <h3 className="text-base font-bold text-foreground truncate">
                  Forensic Query Trace Detail
                </h3>
                {trace && renderOutcomeBadge(trace.record.outcome)}
              </div>
              <div className="text-xs text-muted-foreground font-mono truncate">
                Correlation ID: {trace?.record.correlation_id || correlationId || 'N/A'}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center bg-muted/60 p-0.5 rounded-lg border border-border/40 text-xs">
                <button
                  onClick={() => setActiveTab('visual')}
                  className={`px-2.5 py-1 rounded font-medium transition-colors ${
                    activeTab === 'visual' ? 'bg-surface shadow text-foreground' : 'text-muted-foreground'
                  }`}
                >
                  Visual Breakdown
                </button>
                <button
                  onClick={() => setActiveTab('json')}
                  className={`px-2.5 py-1 rounded font-medium transition-colors ${
                    activeTab === 'json' ? 'bg-surface shadow text-foreground' : 'text-muted-foreground'
                  }`}
                >
                  Raw JSON
                </button>
              </div>

              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                aria-label="Close drawer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Drawer Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
                <RefreshCw className="h-6 w-6 animate-spin text-primary" />
                <span>Loading forensic trace telemetry...</span>
              </div>
            ) : error ? (
              <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-500 text-sm">
                <div className="font-semibold mb-1">Error Loading Trace</div>
                <div>{error}</div>
              </div>
            ) : !trace ? (
              <div className="text-center py-12 text-muted-foreground text-sm">
                No trace telemetry found for this correlation ID.
              </div>
            ) : activeTab === 'json' ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Trace Payload
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleCopyJson}
                    className="flex items-center gap-1.5 text-xs h-7"
                  >
                    {copiedJson ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-500" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" /> Copy JSON
                      </>
                    )}
                  </Button>
                </div>
                <pre className="p-4 bg-surface/90 border border-border/80 rounded-xl font-mono text-xs overflow-x-auto text-foreground max-h-[600px]">
                  {JSON.stringify(trace, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="space-y-6">
                {/* Telemetry Truth Authority Banner */}
                <div
                  className={`p-4 rounded-xl border flex items-start gap-3 ${
                    isAuthoritative
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                      : 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400'
                  }`}
                >
                  {isAuthoritative ? (
                    <ShieldCheck className="h-5 w-5 shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                  )}
                  <div className="space-y-1">
                    <div className="text-sm font-bold flex items-center gap-2">
                      {isAuthoritative ? (
                        <span>[Hardware Telemetry Verified]</span>
                      ) : (
                        <span>[Estimated / Model Approximation]</span>
                      )}
                    </div>
                    <p className="text-xs opacity-90 leading-relaxed">
                      {isAuthoritative
                        ? 'Hardware stage durations recorded directly from database queries, dense Qdrant retrieval, and LLM inference pipelines.'
                        : 'Stage breakdown reconstructed from model execution approximations (historical telemetry record prior to hardware instrumentation).'}
                    </p>
                  </div>
                </div>

                {/* Query Header Info */}
                <div className="p-4 bg-surface/50 border border-border/60 rounded-xl space-y-2">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Audited Query
                  </div>
                  <div className="text-sm font-medium text-foreground">
                    &ldquo;{trace.record.query_text}&rdquo;
                  </div>
                  <div className="flex flex-wrap items-center gap-4 pt-2 text-xs text-muted-foreground border-t border-border/40">
                    <div>
                      Timestamp:{' '}
                      <span className="font-semibold text-foreground">
                        {new Date(trace.record.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div>
                      Total Latency:{' '}
                      <span className="font-mono font-semibold text-foreground">
                        {trace.record.total_duration_ms.toFixed(0)} ms
                      </span>
                    </div>
                    <div>
                      Reliability:{' '}
                      <span className="font-bold text-foreground">
                        {toPresentationPercentage(trace.record.confidence_score).toFixed(1)}%
                      </span>
                    </div>
                    <div>
                      Retry Loops:{' '}
                      <span className="font-semibold text-foreground">
                        {trace.record.retry_attempts}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Stage Latency Waterfall */}
                <div className="space-y-3">
                  <h4 className="text-sm font-bold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
                    <Clock className="h-4 w-4 text-primary" /> Stage Latency Waterfall ({totalDuration.toFixed(0)} ms total)
                  </h4>
                  <div className="space-y-3">
                    {trace.stage_traces.map((stage: StageTraceDTO, idx: number) => {
                      const pct = Math.min(100, Math.max(4, (stage.duration_ms / totalDuration) * 100))
                      const isSuccess = stage.status === 'COMPLETED'
                      const stageAuthoritative = stage.is_authoritative !== false

                      return (
                        <div key={idx} className="space-y-1.5 p-2 rounded-lg bg-surface/40 border border-border/40">
                          <div className="flex justify-between items-center text-xs font-medium">
                            <div className="flex items-center gap-2">
                              <span className="text-foreground font-semibold">{stage.stage_name}</span>
                              {!stageAuthoritative && (
                                <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20 font-mono">
                                  Estimated
                                </span>
                              )}
                            </div>
                            <span className="font-mono text-muted-foreground">
                              {stage.duration_ms.toFixed(1)} ms ({Math.round(pct)}%)
                            </span>
                          </div>
                          <div className="w-full bg-border/40 rounded-full h-2 overflow-hidden flex">
                            <motion.div
                              initial={shouldReduceMotion ? { width: `${pct}%` } : { width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={
                                shouldReduceMotion
                                  ? { duration: 0 }
                                  : { duration: 0.6, delay: idx * 0.05, ease: 'easeOut' }
                              }
                              className={`h-full ${isSuccess ? 'bg-primary' : 'bg-warning'}`}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>

                {/* Confidence Signals & Drivers */}
                {trace.confidence_signals && trace.confidence_signals.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-bold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
                      <Sliders className="h-4 w-4 text-purple-500" /> Confidence Signals & Drivers
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                      {trace.confidence_signals.map((sig: ConfidenceSignalTraceDTO, idx: number) => (
                        <div
                          key={idx}
                          className="p-3 bg-surface/50 border border-border/60 rounded-xl space-y-1.5 shadow-sm"
                        >
                          <div className="flex justify-between items-center text-xs font-bold text-foreground">
                            <span>{sig.signal_name}</span>
                            <span className="text-purple-500 font-mono">
                              {toPresentationPercentage(sig.score).toFixed(1)}%
                            </span>
                          </div>
                          <div className="text-[11px] text-muted-foreground font-medium">
                            Weight: {sig.weight}
                          </div>
                          <p className="text-xs text-muted-foreground pt-1.5 border-t border-border/40 leading-relaxed">
                            {sig.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Retrieved Context Candidates */}
                {trace.retrieval_candidates && trace.retrieval_candidates.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-bold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
                      <Layers className="h-4 w-4 text-emerald-500" /> Retrieved Context Candidates (RRF Merged)
                    </h4>
                    <div className="space-y-3">
                      {trace.retrieval_candidates.map((cand: RetrievalCandidateTraceDTO, idx: number) => (
                        <div
                          key={idx}
                          className="p-3.5 bg-surface border border-border/60 shadow-sm rounded-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                        >
                          <div className="space-y-1.5 max-w-xl">
                            <div className="flex items-center gap-2">
                              <Badge
                                variant="subtle"
                                className="text-[10px] uppercase font-bold tracking-wider text-emerald-600 bg-emerald-500/10 border-emerald-500/20"
                              >
                                Rank #{cand.rrf_rank}
                              </Badge>
                              <span className="text-xs font-mono text-muted-foreground">
                                {cand.chunk_id}
                              </span>
                            </div>
                            <h5 className="text-sm font-semibold text-foreground leading-tight">
                              {cand.document_title}
                            </h5>
                            <p className="text-xs text-muted-foreground italic line-clamp-2 leading-relaxed">
                              &ldquo;{cand.content_snippet}&rdquo;
                            </p>
                          </div>
                          <div className="flex md:flex-col gap-4 md:gap-1.5 text-right text-xs font-mono shrink-0">
                            <div className="text-muted-foreground">
                              Dense: <span className="text-primary font-semibold">{cand.dense_score.toFixed(3)}</span>
                            </div>
                            <div className="text-muted-foreground">
                              Sparse: <span className="text-indigo-500 font-semibold">{cand.sparse_score.toFixed(1)}</span>
                            </div>
                            {cand.rerank_score !== null && (
                              <div className="text-muted-foreground">
                                Rerank:{' '}
                                <span className="font-bold text-emerald-500">
                                  {cand.rerank_score.toFixed(3)}
                                </span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Self-Correction Loops */}
                {trace.self_corrections && trace.self_corrections.length > 0 && (
                  <div className="space-y-3">
                    <h4 className="text-sm font-bold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
                      <RefreshCw className="h-4 w-4 text-warning" /> Self-Correction & Rewrite Loop Diagnostics
                    </h4>
                    <div className="space-y-3">
                      {trace.self_corrections.map((corr: SelfCorrectionTraceDTO, idx: number) => (
                        <div
                          key={idx}
                          className="p-3.5 bg-warning-subtle border border-warning/20 shadow-sm rounded-xl space-y-2 text-xs"
                        >
                          <div className="flex justify-between font-bold text-warning-foreground">
                            <span>Iteration #{corr.attempt_number} — Action: {corr.action_taken}</span>
                            <span className="font-mono">{corr.duration_ms} ms</span>
                          </div>
                          <div className="text-warning-foreground/80 font-medium">Trigger: {corr.trigger_reason}</div>
                          {corr.rewritten_query && (
                            <div className="font-mono bg-background p-2.5 rounded border border-border/40 text-foreground mt-2 leading-relaxed shadow-inner">
                              Rewritten: {corr.rewritten_query}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
