import React, { useEffect, useState } from 'react'
import {
  X,
  Copy,
  Check,
  Activity,
  Layers,
  Clock,
  Search,
  Database,
  Cpu,
} from 'lucide-react'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { dashboardService } from '@/services/dashboardService'
import type { QueryExecutionTraceDTO } from '@/types'

interface ExecutionTraceDrawerProps {
  queryId: string | null
  onClose: () => void
}

export const ExecutionTraceDrawer: React.FC<ExecutionTraceDrawerProps> = ({
  queryId,
  onClose,
}) => {
  const [trace, setTrace] = useState<QueryExecutionTraceDTO | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  useEffect(() => {
    if (!queryId) {
      setTrace(null)
      return
    }

    let isMounted = true
    setIsLoading(true)
    setError(null)

    dashboardService
      .getExecutionTrace(queryId)
      .then((data) => {
        if (isMounted) setTrace(data)
      })
      .catch((err) => {
        if (isMounted) {
          console.error('Failed to load execution trace:', err)
          setError('Unable to fetch detailed forensic trace for this execution.')
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [queryId])

  // Keyboard accessibility: Escape closes drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  if (!queryId) return null

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    setTimeout(() => setCopiedField(null), 2000)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-background/80 backdrop-blur-sm transition-opacity"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Execution Trace Forensics"
    >
      <div
        className="w-full max-w-xl bg-card border-l border-border shadow-2xl flex flex-col h-full overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between p-5 border-b border-border/40 shrink-0 bg-muted/20">
          <div className="flex items-center gap-2.5">
            <Activity className="h-5 w-5 text-primary" />
            <div>
              <h2 className="text-base font-bold text-foreground">Execution Forensics</h2>
              <p className="text-xs text-muted-foreground font-mono">ID: {queryId}</p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
            aria-label="Close trace drawer"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center p-12 text-muted-foreground text-xs">
              <Activity className="h-6 w-6 animate-pulse text-primary mb-2" />
              Loading forensic trace breakdown...
            </div>
          ) : error ? (
            <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
              {error}
            </div>
          ) : !trace ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              Trace information unavailable for this query.
            </div>
          ) : (
            <>
              {/* Outcome & Query Status */}
              <div className="flex items-center justify-between p-3.5 rounded-lg bg-background border border-border/60">
                <div>
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Outcome</span>
                  <Badge
                    variant={
                      trace.outcome === 'SUCCESS'
                        ? 'success'
                        : trace.outcome.includes('ABORTED')
                        ? 'destructive'
                        : 'warning'
                    }
                    className="text-xs font-semibold mt-1"
                  >
                    {trace.outcome}
                  </Badge>
                </div>

                <div className="text-right">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Execution Time</span>
                  <span className="text-xs font-mono text-muted-foreground">
                    {new Date(trace.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>

              {/* Original User Query */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Search className="h-3.5 w-3.5 text-primary" />
                    Input Query Text
                  </span>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(trace.query_text, 'query')}
                    className="text-[11px] text-muted-foreground hover:text-foreground flex items-center gap-1"
                  >
                    {copiedField === 'query' ? (
                      <>
                        <Check className="h-3 w-3 text-emerald-400" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-3 w-3" /> Copy
                      </>
                    )}
                  </button>
                </div>
                <div className="p-3 bg-muted/30 border border-border/40 rounded-lg text-xs font-medium text-foreground leading-relaxed">
                  {trace.query_text}
                </div>
              </div>

              {/* Correlation ID & Audit Link */}
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-background/50 border border-border/40 text-xs">
                <div className="min-w-0">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Correlation ID</span>
                  <span className="font-mono text-[11px] text-foreground truncate block">
                    {trace.correlation_id}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => copyToClipboard(trace.correlation_id, 'corr')}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground shrink-0"
                  aria-label="Copy correlation ID"
                >
                  {copiedField === 'corr' ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>

              {/* Core Telemetry Metrics */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-background border border-border/50 text-xs">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
                    <Clock className="h-3 w-3 text-amber-400" />
                    Duration
                  </span>
                  <span className="font-mono font-bold text-base text-foreground block">
                    {trace.total_duration_ms.toLocaleString()} ms
                  </span>
                  <span className="text-[10px] text-muted-foreground">End-to-end pipeline</span>
                </div>

                <div className="p-3 rounded-lg bg-background border border-border/50 text-xs">
                  <span className="text-[10px] uppercase font-semibold text-muted-foreground flex items-center gap-1 mb-1">
                    <Activity className="h-3 w-3 text-emerald-400" />
                    Reliability Score
                  </span>
                  <span className="font-mono font-bold text-base text-foreground block">
                    {trace.reliability_score !== null ? `${(trace.reliability_score * 100).toFixed(1)}%` : 'N/A'}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    Confidence: {trace.confidence_score !== null ? `${(trace.confidence_score * 100).toFixed(0)}%` : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Hybrid Retrieval Forensic Telemetry */}
              {trace.retrieval ? (
                <div className="space-y-3 p-4 rounded-lg bg-muted/20 border border-border/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      <Layers className="h-3.5 w-3.5 text-sky-400" />
                      Multi-Stage Hybrid Search Radar
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {trace.retrieval.retrieval_duration_ms} ms
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                    <div className="p-2 rounded bg-background border border-border/40">
                      <span className="text-[10px] text-muted-foreground block">Dense</span>
                      <span className="font-mono font-bold text-foreground">
                        {trace.retrieval.dense_candidate_count}
                      </span>
                    </div>

                    <div className="p-2 rounded bg-background border border-border/40">
                      <span className="text-[10px] text-muted-foreground block">Sparse (BM25)</span>
                      <span className="font-mono font-bold text-foreground">
                        {trace.retrieval.sparse_candidate_count}
                      </span>
                    </div>

                    <div className="p-2 rounded bg-background border border-border/40">
                      <span className="text-[10px] text-muted-foreground block">Merged Unique</span>
                      <span className="font-mono font-bold text-foreground">
                        {trace.retrieval.merged_unique_count}
                      </span>
                    </div>

                    <div className="p-2 rounded bg-background border border-border/40">
                      <span className="text-[10px] text-muted-foreground block">Final Top-K</span>
                      <span className="font-mono font-bold text-emerald-400">
                        {trace.retrieval.final_top_k}
                      </span>
                    </div>
                  </div>

                  {/* Stage Latency Decomposition */}
                  {Object.keys(trace.retrieval.stage_breakdown).length > 0 && (
                    <div className="pt-2 border-t border-border/30 space-y-1.5">
                      <span className="text-[10px] uppercase font-semibold text-muted-foreground block">
                        Retrieval Substage Durations
                      </span>
                      <div className="grid grid-cols-2 gap-1.5 font-mono text-[11px]">
                        {Object.entries(trace.retrieval.stage_breakdown).map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between p-1.5 rounded bg-background/60">
                            <span className="text-muted-foreground">{k}:</span>
                            <span className="text-foreground">{typeof v === 'number' ? `${v.toFixed(1)}ms` : String(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-3.5 rounded-lg bg-muted/20 border border-border/40 text-xs text-muted-foreground flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground/60 shrink-0" />
                  <span>No separate multi-stage retrieval log linked for this query.</span>
                </div>
              )}

              {/* Safety & Pipeline Diagnostics */}
              <div className="p-3.5 rounded-lg bg-background border border-border/50 space-y-2 text-xs">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-primary" />
                  Pipeline Integrity Diagnostics
                </span>
                <div className="space-y-1 text-muted-foreground text-[11px]">
                  <div className="flex justify-between">
                    <span>Safety Verification:</span>
                    <span className={trace.is_safe_to_serve ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
                      {trace.is_safe_to_serve ? 'Verified Safe To Serve' : 'Blocked / Unsafe'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Self-Correction Retries:</span>
                    <span className="font-mono text-foreground">{trace.retry_attempts}x attempts</span>
                  </div>
                  {Object.entries(trace.diagnostics).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="capitalize">{k.replace('_', ' ')}:</span>
                      <span className="font-mono text-foreground">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
