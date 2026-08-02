import { useState, useEffect } from 'react'
import {
  Terminal,
  Play,
  Search,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  Layers,
  RefreshCw,
  Sliders,
  ChevronRight,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { PageTransition } from '@/components/layouts'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/common/Card'
import { Input } from '@/components/common/Input'
import { ErrorState } from '@/components/common/ErrorState'
import { analyticsService } from '@/services/analyticsService'
import type {
  QueryTraceDetailDTO,
  QuerySandboxRequestDTO,
  QueryHistoryItemDTO,
  StageTraceDTO,
  RetrievalCandidateTraceDTO,
  ConfidenceSignalTraceDTO,
  SelfCorrectionTraceDTO,
} from '@/types'


export function DeveloperInvestigationPage() {
  const [activeTab, setActiveTab] = useState<'sandbox' | 'trace'>('sandbox')

  // Sandbox state
  const [queryText, setQueryText] = useState('What is the data retention policy for enterprise tenants under SOC 2?')
  const [retrievalStrategy, setRetrievalStrategy] = useState('hybrid')
  const [topK, setTopK] = useState(5)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.75)
  const [enableReranking, setEnableReranking] = useState(true)
  const [enableSelfCorrection, setEnableSelfCorrection] = useState(true)
  const [isExecuting, setIsExecuting] = useState(false)
  const [sandboxTrace, setSandboxTrace] = useState<QueryTraceDetailDTO | null>(null)
  const [sandboxAnswer, setSandboxAnswer] = useState<string | null>(null)
  const [sandboxOutcome, setSandboxOutcome] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Trace Browser state
  const [historyItems, setHistoryItems] = useState<QueryHistoryItemDTO[]>([])
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [inspectedTrace, setInspectedTrace] = useState<QueryTraceDetailDTO | null>(null)
  const [isLoadingTrace, setIsLoadingTrace] = useState(false)
  const [searchFilter, setSearchFilter] = useState('')

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
      setSandboxOutcome(response.outcome)
      setSandboxAnswer(response.final_answer)
      setSandboxTrace(response.trace_detail)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to execute sandbox query')
    } finally {
      setIsExecuting(false)
    }
  }

  const loadHistory = async () => {
    setIsLoadingHistory(true)
    try {
      const res = await analyticsService.getQueryHistory(1, 30)
      setHistoryItems(res.items || [])
    } catch (err) {
      console.error('Failed to load query history', err)
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const loadTraceDetail = async (correlationId: string) => {
    setSelectedTraceId(correlationId)
    setIsLoadingTrace(true)
    try {
      const detail = await analyticsService.getQueryTraceDetail(correlationId)
      setInspectedTrace(detail)
    } catch (err) {
      console.error('Failed to inspect trace', err)
    } finally {
      setIsLoadingTrace(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'trace') {
      loadHistory()
    }
  }, [activeTab])

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
            <AlertTriangle className="h-3.5 w-3.5" /> CLARIFICATION REQUIRED
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

  const renderTraceWaterfall = (trace: QueryTraceDetailDTO) => {
    const totalMs = trace.record.total_duration_ms || 1
    return (
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
          <Clock className="h-4 w-4 text-primary" /> Stage Latency Waterfall ({totalMs} ms total)
        </h4>
        <div className="space-y-3">
          {trace.stage_traces.map((stage: StageTraceDTO, idx: number) => {
            const pct = Math.min(100, Math.max(5, (stage.duration_ms / totalMs) * 100))
            const isSuccess = stage.status === 'COMPLETED'
            return (
              <div key={idx} className="space-y-1.5">
                <div className="flex justify-between text-xs font-medium">
                  <span className="text-foreground">{stage.stage_name}</span>
                  <span className="font-mono text-muted-foreground">{stage.duration_ms} ms ({Math.round(pct)}%)</span>
                </div>
                <div className="w-full bg-border/40 rounded-full h-2 overflow-hidden flex">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, delay: idx * 0.1, ease: 'easeOut' }}
                    className={`h-full transition-colors ${
                      isSuccess ? 'bg-primary' : 'bg-warning'
                    }`}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const renderConfidenceSignals = (trace: QueryTraceDetailDTO) => (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
        <Sliders className="h-4 w-4 text-purple-500" /> Confidence Signals & Drivers
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {trace.confidence_signals.map((sig: ConfidenceSignalTraceDTO, idx: number) => (
          <div
            key={idx}
            className="p-3 bg-surface/50 border border-border/60 rounded-xl space-y-1.5 shadow-sm"
          >
            <div className="flex justify-between items-center text-xs font-bold text-foreground">
              <span>{sig.signal_name}</span>
              <span className="text-purple-500 font-mono">
                {(sig.score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground font-medium">Weight: {sig.weight}</div>
            <p className="text-xs text-muted-foreground pt-1.5 border-t border-border/40 leading-relaxed">
              {sig.explanation}
            </p>
          </div>
        ))}
      </div>
    </div>
  )

  const renderRetrievalCandidates = (trace: QueryTraceDetailDTO) => (
    <div className="space-y-4">
      <h4 className="text-sm font-semibold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
        <Layers className="h-4 w-4 text-emerald-500" /> Retrieved Context Candidates (RRF Merged)
      </h4>
      <div className="space-y-3">
        {trace.retrieval_candidates.map((cand: RetrievalCandidateTraceDTO, idx: number) => (
          <div
            key={idx}
            className="p-3.5 bg-surface border border-border/60 shadow-sm rounded-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition-colors hover:border-border"
          >
            <div className="space-y-1.5 max-w-2xl">
              <div className="flex items-center gap-2">
                <Badge variant="subtle" className="text-[10px] uppercase font-bold tracking-wider text-emerald-600 bg-emerald-500/10 border-emerald-500/20">
                  Rank #{cand.rrf_rank}
                </Badge>
                <span className="text-xs font-mono text-muted-foreground">{cand.chunk_id}</span>
              </div>
              <h5 className="text-sm font-semibold text-foreground leading-tight">{cand.document_title}</h5>
              <p className="text-xs text-muted-foreground italic line-clamp-2 leading-relaxed">
                &ldquo;{cand.content_snippet}&rdquo;
              </p>
            </div>
            <div className="flex md:flex-col gap-4 md:gap-1.5 text-right text-xs font-mono shrink-0">
              <div className="text-muted-foreground">Dense: <span className="text-primary font-semibold">{cand.dense_score.toFixed(3)}</span></div>
              <div className="text-muted-foreground">Sparse: <span className="text-indigo-500 font-semibold">{cand.sparse_score.toFixed(1)}</span></div>
              {cand.rerank_score !== null && (
                <div className="text-muted-foreground">Rerank: <span className="font-bold text-emerald-500">{cand.rerank_score.toFixed(3)}</span></div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )

  const renderSelfCorrections = (trace: QueryTraceDetailDTO) => {
    if (!trace.self_corrections || trace.self_corrections.length === 0) return null
    return (
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-foreground flex items-center gap-2 border-b border-border/40 pb-2">
          <RefreshCw className="h-4 w-4 text-warning animate-spin-subtle" /> Self-Correction & Rewrite Loop Diagnostics
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
    )
  }

  const filteredHistory = historyItems.filter(
    (item) =>
      item.correlation_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
      item.query_text.toLowerCase().includes(searchFilter.toLowerCase())
  )

  return (
    <PageTransition className="space-y-8 max-w-7xl mx-auto pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/60 pb-6">
        <PageHeader
          title="Developer Investigation Console"
          description="Deep-dive forensic debugging suite for RAGuard AI queries, multi-stage waterfalls, RRF rankings, and self-correction traces."
        />

        <div className="flex bg-surface border border-border p-1 rounded-lg shadow-sm shrink-0">
          <button
            onClick={() => setActiveTab('sandbox')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-bold transition-all ${
              activeTab === 'sandbox'
                ? 'bg-primary text-primary-foreground shadow'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <Play className="h-4 w-4" /> Sandbox
          </button>
          <button
            onClick={() => setActiveTab('trace')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-bold transition-all ${
              activeTab === 'trace'
                ? 'bg-primary text-primary-foreground shadow'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            }`}
          >
            <Search className="h-4 w-4" /> Trace Browser
          </button>
        </div>
      </div>

      {error && (
        <ErrorState
          title="Execution Error"
          error={new Error(error)}
          className="mb-8"
        />
      )}

      {/* Sandbox Playground Tab */}
      {activeTab === 'sandbox' && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          {/* Controls Panel */}
          <Card className="xl:col-span-4 h-fit shadow-card">
            <CardHeader className="border-b border-border/40 pb-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sliders className="h-4 w-4 text-primary" /> Sandbox Parameters
              </CardTitle>
              <CardDescription>
                Tune hybrid retrieval weights, safety bounds, and cross-encoder pipelines.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-5 space-y-6">
              <div className="space-y-2">
                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                  Test Query
                </label>
                <textarea
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  rows={3}
                  placeholder="Enter test query..."
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all resize-none shadow-inner"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                  Retrieval Strategy
                </label>
                <select
                  value={retrievalStrategy}
                  onChange={(e) => setRetrievalStrategy(e.target.value)}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary transition-all shadow-sm"
                >
                  <option value="hybrid">Hybrid (Dense + Sparse + RRF)</option>
                  <option value="dense_only">Dense Vector Only</option>
                  <option value="sparse_only">Sparse BM25 Only</option>
                </select>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="font-bold text-foreground">Top-K Candidates</span>
                  <span className="font-mono font-bold text-primary bg-primary-subtle px-1.5 rounded">{topK}</span>
                </div>
                <input
                  type="range"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                />
              </div>

              <div className="space-y-3">
                <div className="flex justify-between text-xs">
                  <span className="font-bold text-foreground">Safety Threshold</span>
                  <span className="font-mono font-bold text-purple-500 bg-purple-500/10 px-1.5 rounded">{confidenceThreshold}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-purple-500"
                />
              </div>

              <div className="space-y-4 pt-4 border-t border-border/40">
                <label className="flex items-center gap-3 text-sm text-foreground font-medium cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={enableReranking}
                    onChange={(e) => setEnableReranking(e.target.checked)}
                    className="w-4 h-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-0 bg-background"
                  />
                  <span className="group-hover:text-primary transition-colors">Cross-Encoder Reranking</span>
                </label>

                <label className="flex items-center gap-3 text-sm text-foreground font-medium cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={enableSelfCorrection}
                    onChange={(e) => setEnableSelfCorrection(e.target.checked)}
                    className="w-4 h-4 rounded border-border text-primary focus:ring-primary focus:ring-offset-0 bg-background"
                  />
                  <span className="group-hover:text-primary transition-colors">Self-Correction Loop</span>
                </label>
              </div>

              <Button
                variant="default"
                onClick={handleExecuteSandbox}
                isLoading={isExecuting}
                disabled={isExecuting || !queryText.trim()}
                className="w-full flex justify-center items-center gap-2"
              >
                {!isExecuting && <Play className="h-4 w-4" />}
                Execute Sandbox Query
              </Button>
            </CardContent>
          </Card>

          {/* Trace Diagnostics Panel */}
          <div className="xl:col-span-8">
            {!sandboxTrace ? (
              <div className="h-full min-h-[400px] flex items-center justify-center">
                <div className="text-center space-y-4 max-w-sm">
                  <div className="h-16 w-16 mx-auto rounded-full bg-muted flex items-center justify-center text-muted-foreground/50">
                    <Terminal className="h-8 w-8" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    Ready for Forensic Execution
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Configure your query and retrieval parameters on the left, then click <strong>Execute Sandbox Query</strong> to inspect multi-stage execution metrics.
                  </p>
                </div>
              </div>
            ) : (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                {/* Result Card */}
                <Card className="shadow-card">
                  <CardContent className="p-5 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border/40">
                      <div className="flex items-center gap-4">
                        {renderOutcomeBadge(sandboxOutcome || 'UNKNOWN')}
                        <span className="text-xs font-mono text-muted-foreground font-medium">
                          ID: {sandboxTrace.record.correlation_id}
                        </span>
                      </div>
                      <div className="flex items-center gap-5 text-xs font-bold">
                        <div className="text-muted-foreground">Confidence: <span className="text-primary font-mono ml-1">{(sandboxTrace.record.confidence_score ?? 0 * 100).toFixed(1)}%</span></div>
                        <div className="text-muted-foreground">Reliability: <span className="text-success font-mono ml-1">{sandboxTrace.record.reliability_score?.toFixed(1)}/100</span></div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Generated Response</span>
                      <div className="p-4 bg-background rounded-xl border border-border shadow-inner text-sm text-foreground font-medium leading-relaxed">
                        {sandboxAnswer}
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Detailed Trace Sections */}
                <Card className="shadow-card">
                  <CardContent className="p-6 space-y-8">
                    {renderTraceWaterfall(sandboxTrace)}
                    {renderConfidenceSignals(sandboxTrace)}
                    {renderRetrievalCandidates(sandboxTrace)}
                    {sandboxTrace.self_corrections && sandboxTrace.self_corrections.length > 0 && (
                      renderSelfCorrections(sandboxTrace)
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      )}

      {/* Trace Browser Tab */}
      {activeTab === 'trace' && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          {/* History List */}
          <Card className="xl:col-span-5 h-fit max-h-[800px] flex flex-col shadow-card">
            <CardHeader className="border-b border-border/40 pb-4 shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-primary" /> Execution Logs
                </CardTitle>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={loadHistory}
                  isLoading={isLoadingHistory}
                  className="h-8 w-8 p-0 flex items-center justify-center"
                >
                  {!isLoadingHistory && <RefreshCw className="h-3.5 w-3.5" />}
                </Button>
              </div>
              <div className="pt-4">
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search traces..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="pl-9 h-9 text-xs"
                  />
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-0 overflow-y-auto flex-1">
              {isLoadingHistory ? (
                <div className="p-12 flex flex-col items-center justify-center text-muted-foreground space-y-3">
                  <RefreshCw className="h-6 w-6 animate-spin" />
                  <span className="text-sm">Loading logs...</span>
                </div>
              ) : filteredHistory.length === 0 ? (
                <div className="p-12 text-center text-sm text-muted-foreground">No matching query traces found.</div>
              ) : (
                <div className="divide-y divide-border/40">
                  {filteredHistory.map((item) => {
                    const isSelected = selectedTraceId === item.correlation_id
                    return (
                      <div
                        key={item.id}
                        onClick={() => loadTraceDetail(item.correlation_id)}
                        className={`p-4 transition-colors cursor-pointer space-y-2 ${
                          isSelected
                            ? 'bg-primary-subtle hover:bg-primary-subtle'
                            : 'hover:bg-muted/50'
                        }`}
                      >
                        <div className="flex justify-between items-center gap-3">
                          {renderOutcomeBadge(item.outcome)}
                          <span className="text-[10px] font-mono text-muted-foreground truncate max-w-[140px] font-medium">
                            {item.correlation_id}
                          </span>
                        </div>
                        <p className={`text-sm font-semibold line-clamp-1 ${isSelected ? 'text-primary' : 'text-foreground'}`}>
                          {item.query_text}
                        </p>
                        <div className="flex justify-between items-center text-[11px] text-muted-foreground font-mono pt-1">
                          <span className="font-medium text-foreground">{item.total_duration_ms} ms</span>
                          <span className="font-medium">Conf: {item.confidence_score ? `${(item.confidence_score * 100).toFixed(0)}%` : 'N/A'}</span>
                          <div className={`flex items-center font-bold ${isSelected ? 'text-primary' : 'text-foreground group-hover:text-primary'}`}>
                            Inspect <ChevronRight className="h-3.5 w-3.5 ml-0.5" />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Inspected Trace Diagnostics */}
          <div className="xl:col-span-7">
            {!inspectedTrace ? (
              <div className="h-full min-h-[400px] flex items-center justify-center">
                <div className="text-center space-y-4 max-w-sm">
                  <div className="h-16 w-16 mx-auto rounded-full bg-muted flex items-center justify-center text-muted-foreground/50">
                    <Search className="h-8 w-8" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground">
                    Select a Trace
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Click on any query execution log from the left pane to view its stage latency waterfall, candidate breakdowns, and confidence signals.
                  </p>
                </div>
              </div>
            ) : isLoadingTrace ? (
              <div className="h-full min-h-[400px] flex items-center justify-center text-muted-foreground space-y-3 flex-col">
                <RefreshCw className="h-6 w-6 animate-spin" />
                <span className="text-sm font-medium">Loading deep-dive forensic diagnostics...</span>
              </div>
            ) : (
              <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="space-y-6">
                <Card className="shadow-card">
                  <CardContent className="p-6 space-y-8">
                    <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pb-6 border-b border-border/40">
                      <div className="space-y-3">
                        <div className="flex items-center gap-3">
                          {renderOutcomeBadge(inspectedTrace.record.outcome)}
                          <span className="text-[11px] font-mono text-muted-foreground font-medium bg-muted px-2 py-1 rounded">
                            {inspectedTrace.record.correlation_id}
                          </span>
                        </div>
                        <h3 className="text-lg font-bold text-foreground leading-snug">
                          &ldquo;{inspectedTrace.record.query_text}&rdquo;
                        </h3>
                      </div>
                      <div className="flex md:flex-col gap-4 md:gap-1.5 md:text-right text-xs font-mono shrink-0">
                        <div className="text-muted-foreground">Duration: <span className="font-bold text-foreground text-sm ml-1">{inspectedTrace.record.total_duration_ms} ms</span></div>
                        <div className="text-muted-foreground">Reliability: <span className="font-bold text-success text-sm ml-1">{inspectedTrace.record.reliability_score?.toFixed(1)}</span></div>
                      </div>
                    </div>

                    {renderTraceWaterfall(inspectedTrace)}
                    {renderConfidenceSignals(inspectedTrace)}
                    {renderRetrievalCandidates(inspectedTrace)}
                    {inspectedTrace.self_corrections && inspectedTrace.self_corrections.length > 0 && (
                      renderSelfCorrections(inspectedTrace)
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </div>
        </div>
      )}
    </PageTransition>
  )
}
