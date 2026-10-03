import { useState } from 'react'
import {
  Play,
  Terminal,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Sliders,
  RefreshCw,
  Search,
} from 'lucide-react'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { analyticsService } from '@/services/analyticsService'
import { toPresentationPercentage } from '@/utils/telemetryAdapters'
import type { QuerySandboxRequestDTO, QuerySandboxResponseDTO } from '@/types'

interface DiagnosticSandboxTabProps {
  onInspectTrace: (trace: QuerySandboxResponseDTO) => void
}

export function DiagnosticSandboxTab({ onInspectTrace }: DiagnosticSandboxTabProps) {
  const [queryText, setQueryText] = useState(
    'What is the data retention policy for enterprise tenants under SOC 2?'
  )
  const [retrievalStrategy, setRetrievalStrategy] = useState('hybrid')
  const [topK, setTopK] = useState(5)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.75)
  const [enableReranking, setEnableReranking] = useState(true)
  const [enableSelfCorrection, setEnableSelfCorrection] = useState(true)
  const [isExecuting, setIsExecuting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<QuerySandboxResponseDTO | null>(null)

  const handleExecuteSandbox = async () => {
    if (!queryText.trim()) return
    setIsExecuting(true)
    setError(null)
    try {
      const payload: QuerySandboxRequestDTO = {
        query_text: queryText,
        retrieval_strategy: retrievalStrategy,
        top_k: topK,
        confidence_threshold: confidenceThreshold,
        enable_reranking: enableReranking,
        enable_self_correction: enableSelfCorrection,
      }
      const response = await analyticsService.executeSandboxQuery(payload)
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute diagnostic sandbox query')
    } finally {
      setIsExecuting(false)
    }
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

  return (
    <div className="space-y-6">
      {/* Simulation / Sandbox Mode Notice */}
      <div className="p-4 bg-indigo-500/10 border border-indigo-500/30 rounded-xl flex items-start gap-3">
        <Terminal className="h-5 w-5 text-indigo-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="text-sm font-bold text-foreground flex items-center gap-2">
            <span>[Simulation & Dry-Run Mode]</span>
            <Badge variant="subtle" className="text-[10px] bg-indigo-500/20 text-indigo-400 border-none font-mono">
              Non-Mutating Sandbox
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Execute ad-hoc diagnostic tests against real retrieval vectors and scoring models without polluting
            live user session logs or customer conversation histories. Hardware timings and stage traces are generated in dry-run mode.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Query Configurator */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-bold flex items-center gap-2">
                <Sliders className="h-4.5 w-4.5 text-primary" />
                Pipeline Test Parameters
              </CardTitle>
              <CardDescription className="text-xs text-muted-foreground mt-0.5">
                Customize retrieval strategy, ranking thresholds, and self-correction loops
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-4 space-y-4">
              {/* Test Query Input */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Diagnostic Test Query
                </label>
                <textarea
                  rows={3}
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  placeholder="Enter query to simulate pipeline execution..."
                  className="w-full rounded-lg border border-border/60 bg-surface p-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary resize-none"
                />
              </div>

              {/* Retrieval Strategy */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">
                  Retrieval Strategy
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['hybrid', 'dense_only', 'sparse_only'] as const).map((strategy) => (
                    <button
                      key={strategy}
                      type="button"
                      onClick={() => setRetrievalStrategy(strategy)}
                      className={`py-1.5 px-2 rounded-lg text-xs font-medium border capitalize transition-colors ${
                        retrievalStrategy === strategy
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-surface text-muted-foreground border-border/60 hover:text-foreground'
                      }`}
                    >
                      {strategy.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              {/* Top-K Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-foreground">Top-K Candidates</span>
                  <span className="font-mono text-primary font-bold">{topK}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={20}
                  step={1}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-full accent-primary h-1.5 bg-border rounded-lg cursor-pointer"
                />
              </div>

              {/* Confidence Threshold Slider */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-foreground">Confidence Threshold</span>
                  <span className="font-mono text-primary font-bold">
                    {(confidenceThreshold * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min={0.1}
                  max={0.95}
                  step={0.05}
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="w-full accent-primary h-1.5 bg-border rounded-lg cursor-pointer"
                />
              </div>

              {/* Toggles */}
              <div className="space-y-2 pt-2 border-t border-border/40">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground">
                  <input
                    type="checkbox"
                    checked={enableReranking}
                    onChange={(e) => setEnableReranking(e.target.checked)}
                    className="accent-primary rounded h-4 w-4"
                  />
                  <span>Enable Cross-Encoder Reranking</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-foreground">
                  <input
                    type="checkbox"
                    checked={enableSelfCorrection}
                    onChange={(e) => setEnableSelfCorrection(e.target.checked)}
                    className="accent-primary rounded h-4 w-4"
                  />
                  <span>Enable Self-Correction & Rewrite Loop</span>
                </label>
              </div>

              {/* Run Button */}
              <Button
                onClick={handleExecuteSandbox}
                disabled={isExecuting || !queryText.trim()}
                className="w-full flex items-center justify-center gap-2 py-2 text-xs font-bold"
              >
                {isExecuting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" /> Running Simulation...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" /> Run Sandbox Dry-Run
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Execution Output */}
        <div className="lg:col-span-7 space-y-4">
          <Card className="border-border/60 bg-surface/60 backdrop-blur-xl shadow-lg min-h-[440px] flex flex-col">
            <CardHeader className="pb-3 border-b border-border/40 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-base font-bold flex items-center gap-2">
                  <Terminal className="h-4.5 w-4.5 text-primary" />
                  Simulation Output & Verification
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground mt-0.5">
                  Real-time dry-run outcome, response preview, and telemetry trace
                </CardDescription>
              </div>
              {result && renderOutcomeBadge(result.outcome)}
            </CardHeader>

            <CardContent className="pt-4 flex-1 flex flex-col justify-between">
              {error ? (
                <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-500 text-xs">
                  <div className="font-bold mb-1">Execution Error</div>
                  <div>{error}</div>
                </div>
              ) : !result ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-muted-foreground">
                  <Terminal className="h-10 w-10 mb-3 text-muted-foreground/40" />
                  <p className="text-sm font-semibold">No Sandbox Run Executed</p>
                  <p className="text-xs mt-1 max-w-sm">
                    Configure your diagnostic parameters on the left and click &ldquo;Run Sandbox Dry-Run&rdquo; to simulate pipeline verification.
                  </p>
                </div>
              ) : (
                <div className="space-y-4 flex-1">
                  {/* Quick Telemetry Banner */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="p-2.5 rounded-lg bg-surface border border-border/50 text-xs">
                      <div className="text-muted-foreground">Confidence Score</div>
                      <div className="font-bold text-foreground text-sm mt-0.5">
                        {toPresentationPercentage(result.trace_detail.record.confidence_score).toFixed(1)}%
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-surface border border-border/50 text-xs">
                      <div className="text-muted-foreground">Total Latency</div>
                      <div className="font-mono font-bold text-foreground text-sm mt-0.5">
                        {result.trace_detail.record.total_duration_ms.toFixed(0)} ms
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-surface border border-border/50 text-xs">
                      <div className="text-muted-foreground">Candidates Yield</div>
                      <div className="font-bold text-foreground text-sm mt-0.5">
                        {result.trace_detail.retrieval_candidates?.length || 0} chunks
                      </div>
                    </div>
                  </div>

                  {/* Final Answer Preview */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-foreground">
                      Grounded Answer Preview
                    </label>
                    <div className="p-3 bg-surface/80 border border-border/60 rounded-xl text-xs text-foreground leading-relaxed max-h-48 overflow-y-auto">
                      {result.final_answer || 'No answer generated.'}
                    </div>
                  </div>

                  {/* Stage Summary */}
                  <div className="space-y-1.5">
                    <div className="text-xs font-semibold text-foreground">
                      Stage Execution
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      {result.trace_detail.stage_traces.map((stage, idx) => (
                        <div
                          key={idx}
                          className="p-2 bg-surface border border-border/40 rounded-lg flex justify-between items-center"
                        >
                          <span className="text-muted-foreground truncate">{stage.stage_name}</span>
                          <span className="font-mono font-semibold text-foreground">
                            {stage.duration_ms.toFixed(0)} ms
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Inspect Button */}
                  <div className="pt-2">
                    <Button
                      variant="outline"
                      onClick={() => onInspectTrace(result)}
                      className="w-full flex items-center justify-center gap-2 py-2 text-xs font-bold"
                    >
                      <Search className="h-3.5 w-3.5" /> Inspect Full Forensic Trace Waterfall
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
