import React, { useState, useEffect } from 'react'
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
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Card } from '@/components/common/Card'
import { Input } from '@/components/common/Input'
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

export const DeveloperInvestigationPage: React.FC = () => {
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
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" /> SUCCESS
          </Badge>
        )
      case 'CLARIFICATION_REQUIRED':
        return (
          <Badge variant="warning" className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> CLARIFICATION REQUIRED
          </Badge>
        )
      default:
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="h-3 w-3" /> {outcome}
          </Badge>
        )
    }
  }

  const renderTraceWaterfall = (trace: QueryTraceDetailDTO) => {
    const totalMs = trace.record.total_duration_ms || 1
    return (
      <div className="space-y-4">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <Clock className="h-4 w-4 text-blue-500" /> Stage Latency Waterfall ({totalMs} ms total)
        </h4>
        <div className="space-y-3">
          {trace.stage_traces.map((stage: StageTraceDTO, idx: number) => {
            const pct = Math.min(100, Math.max(5, (stage.duration_ms / totalMs) * 100))
            return (
              <div key={idx} className="space-y-1">
                <div className="flex justify-between text-xs text-gray-700 dark:text-gray-300">
                  <span className="font-medium">{stage.stage_name}</span>
                  <span className="font-mono text-gray-500">{stage.duration_ms} ms ({Math.round(pct)}%)</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      stage.status === 'COMPLETED'
                        ? 'bg-gradient-to-r from-blue-500 to-indigo-500'
                        : 'bg-gradient-to-r from-amber-500 to-red-500'
                    }`}
                    style={{ width: `${pct}%` }}
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
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <Sliders className="h-4 w-4 text-purple-500" /> Confidence Signals & Drivers
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {trace.confidence_signals.map((sig: ConfidenceSignalTraceDTO, idx: number) => (
          <div
            key={idx}
            className="p-3 bg-gray-50 dark:bg-gray-800/60 border border-gray-200 dark:border-gray-700 rounded-lg space-y-1"
          >
            <div className="flex justify-between items-center text-xs font-semibold text-gray-800 dark:text-gray-200">
              <span>{sig.signal_name}</span>
              <span className="text-purple-600 dark:text-purple-400 font-mono">
                {(sig.score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="text-[11px] text-gray-500 dark:text-gray-400">Weight: {sig.weight}</div>
            <p className="text-xs text-gray-600 dark:text-gray-300 pt-1 border-t border-gray-200 dark:border-gray-700/50">
              {sig.explanation}
            </p>
          </div>
        ))}
      </div>
    </div>
  )

  const renderRetrievalCandidates = (trace: QueryTraceDetailDTO) => (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
        <Layers className="h-4 w-4 text-emerald-500" /> Retrieved Context Candidates (RRF Merged)
      </h4>
      <div className="space-y-2">
        {trace.retrieval_candidates.map((cand: RetrievalCandidateTraceDTO, idx: number) => (
          <div
            key={idx}
            className="p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
          >
            <div className="space-y-1 max-w-2xl">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 text-xs font-bold rounded">
                  Rank #{cand.rrf_rank}
                </span>
                <span className="text-xs font-mono text-gray-400">{cand.chunk_id}</span>
              </div>
              <h5 className="text-sm font-medium text-gray-900 dark:text-white">{cand.document_title}</h5>
              <p className="text-xs text-gray-600 dark:text-gray-300 italic line-clamp-2">
                &ldquo;{cand.content_snippet}&rdquo;
              </p>
            </div>
            <div className="flex md:flex-col gap-3 md:gap-1 text-right text-xs font-mono shrink-0">
              <div>Dense: <span className="text-blue-600 dark:text-blue-400">{cand.dense_score.toFixed(3)}</span></div>
              <div>Sparse: <span className="text-indigo-600 dark:text-indigo-400">{cand.sparse_score.toFixed(1)}</span></div>
              {cand.rerank_score !== null && (
                <div>Rerank: <span className="font-bold text-emerald-600 dark:text-emerald-400">{cand.rerank_score.toFixed(3)}</span></div>
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
      <div className="space-y-3">
        <h4 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <RefreshCw className="h-4 w-4 text-amber-500 animate-spin-slow" /> Self-Correction & Rewrite Loop Diagnostics
        </h4>
        <div className="space-y-2">
          {trace.self_corrections.map((corr: SelfCorrectionTraceDTO, idx: number) => (
            <div
              key={idx}
              className="p-3 bg-amber-50/50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/60 rounded-lg space-y-1 text-xs"
            >
              <div className="flex justify-between font-semibold text-amber-900 dark:text-amber-200">
                <span>Iteration #{corr.attempt_number} — Action: {corr.action_taken}</span>
                <span>{corr.duration_ms} ms</span>
              </div>
              <div className="text-gray-700 dark:text-gray-300">Trigger: {corr.trigger_reason}</div>
              {corr.rewritten_query && (
                <div className="font-mono bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-200 mt-1">
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
    <div className="space-y-6 max-w-7xl mx-auto p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 dark:border-gray-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Terminal className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
              Developer Investigation Console
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Deep-dive forensic debugging suite for RAGuard AI queries, multi-stage waterfalls, RRF rankings, and self-correction traces.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={activeTab === 'sandbox' ? 'default' : 'outline'}
            onClick={() => setActiveTab('sandbox')}
            className="flex items-center gap-1.5"
          >
            <Play className="h-4 w-4" /> Sandbox Playground
          </Button>
          <Button
            variant={activeTab === 'trace' ? 'default' : 'outline'}
            onClick={() => setActiveTab('trace')}
            className="flex items-center gap-1.5"
          >
            <Search className="h-4 w-4" /> Forensic Trace Browser
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg flex items-center gap-3 text-sm text-red-800 dark:text-red-300">
          <XCircle className="h-5 w-5 text-red-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Sandbox Playground Tab */}
      {activeTab === 'sandbox' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls Panel */}
          <Card className="lg:col-span-4 p-5 space-y-5 h-fit border-gray-200 dark:border-gray-800">
            <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Sliders className="h-4 w-4 text-blue-500" /> Sandbox Parameters
            </h3>

            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">
                Test Query
              </label>
              <textarea
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                rows={3}
                placeholder="Enter test query..."
                className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-gray-600 dark:text-gray-400">
                Retrieval Strategy
              </label>
              <select
                value={retrievalStrategy}
                onChange={(e) => setRetrievalStrategy(e.target.value)}
                className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="hybrid">Hybrid (Dense + Sparse + RRF)</option>
                <option value="dense_only">Dense Vector Only</option>
                <option value="sparse_only">Sparse BM25 Only</option>
              </select>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-700 dark:text-gray-300">
                <span className="font-semibold uppercase tracking-wider">Top-K Candidates</span>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400">{topK}</span>
              </div>
              <input
                type="range"
                min={1}
                max={20}
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-blue-600"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-700 dark:text-gray-300">
                <span className="font-semibold uppercase tracking-wider">Confidence Safety Threshold</span>
                <span className="font-mono font-bold text-purple-600 dark:text-purple-400">{confidenceThreshold}</span>
              </div>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                className="w-full accent-purple-600"
              />
            </div>

            <div className="space-y-3 pt-2 border-t border-gray-200 dark:border-gray-700">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableReranking}
                  onChange={(e) => setEnableReranking(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Enable Cross-Encoder Reranking</span>
              </label>

              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableSelfCorrection}
                  onChange={(e) => setEnableSelfCorrection(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span>Enable Self-Correction & Rewrite Loop</span>
              </label>
            </div>

            <Button
              variant="default"
              onClick={handleExecuteSandbox}
              disabled={isExecuting || !queryText.trim()}
              className="w-full flex justify-center items-center gap-2 py-2.5 shadow-md"
            >
              {isExecuting ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" /> Executing Forensic Trace...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" /> Execute Sandbox Query
                </>
              )}
            </Button>
          </Card>

          {/* Trace Diagnostics Panel */}
          <div className="lg:col-span-8 space-y-6">
            {!sandboxTrace ? (
              <Card className="p-12 text-center border-dashed border-2 border-gray-300 dark:border-gray-700 space-y-3">
                <Terminal className="h-12 w-12 text-gray-400 mx-auto opacity-50" />
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300">
                  Ready for Forensic Execution
                </h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto">
                  Configure your query and retrieval parameters on the left, then click &ldquo;Execute Sandbox Query&rdquo; to inspect multi-stage execution metrics.
                </p>
              </Card>
            ) : (
              <div className="space-y-6">
                {/* Result Card */}
                <Card className="p-5 border-gray-200 dark:border-gray-800 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-gray-200 dark:border-gray-700/50">
                    <div className="flex items-center gap-3">
                      {renderOutcomeBadge(sandboxOutcome || 'UNKNOWN')}
                      <span className="text-xs font-mono text-gray-500">
                        Correlation ID: {sandboxTrace.record.correlation_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs font-semibold">
                      <div>Confidence: <span className="text-blue-600 dark:text-blue-400 font-mono">{(sandboxTrace.record.confidence_score! * 100).toFixed(1)}%</span></div>
                      <div>Reliability: <span className="text-emerald-600 dark:text-emerald-400 font-mono">{sandboxTrace.record.reliability_score?.toFixed(1)}/100</span></div>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Generated Response</span>
                    <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-800 text-sm text-gray-800 dark:text-gray-200 font-medium leading-relaxed">
                      {sandboxAnswer}
                    </div>
                  </div>
                </Card>

                {/* Detailed Trace Sections */}
                <Card className="p-5 border-gray-200 dark:border-gray-800 space-y-6">
                  {renderTraceWaterfall(sandboxTrace)}
                  <hr className="border-gray-200 dark:border-gray-700" />
                  {renderConfidenceSignals(sandboxTrace)}
                  <hr className="border-gray-200 dark:border-gray-700" />
                  {renderRetrievalCandidates(sandboxTrace)}
                  {sandboxTrace.self_corrections && sandboxTrace.self_corrections.length > 0 && (
                    <>
                      <hr className="border-gray-200 dark:border-gray-700" />
                      {renderSelfCorrections(sandboxTrace)}
                    </>
                  )}
                </Card>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Trace Browser Tab */}
      {activeTab === 'trace' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* History List */}
          <Card className="lg:col-span-5 p-5 space-y-4 border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <FileText className="h-4 w-4 text-blue-500" /> Recent Execution Logs
              </h3>
              <Button
                variant="outline"
                size="sm"
                onClick={loadHistory}
                disabled={isLoadingHistory}
                className="h-8 px-2"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoadingHistory ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            <Input
              placeholder="Search by text or correlation ID..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="text-xs"
            />

            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {isLoadingHistory ? (
                <div className="p-8 text-center text-sm text-gray-500 animate-pulse">Loading execution history...</div>
              ) : filteredHistory.length === 0 ? (
                <div className="p-8 text-center text-sm text-gray-500">No matching query traces found.</div>
              ) : (
                filteredHistory.map((item) => {
                  const isSelected = selectedTraceId === item.correlation_id
                  return (
                    <div
                      key={item.id}
                      onClick={() => loadTraceDetail(item.correlation_id)}
                      className={`p-3 rounded-lg border transition-all cursor-pointer space-y-2 ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/30 shadow-sm'
                          : 'border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 hover:border-gray-300 dark:hover:border-gray-700'
                      }`}
                    >
                      <div className="flex justify-between items-center gap-2">
                        {renderOutcomeBadge(item.outcome)}
                        <span className="text-[11px] font-mono text-gray-400 truncate max-w-[140px]">
                          {item.correlation_id}
                        </span>
                      </div>
                      <p className="text-xs font-medium text-gray-900 dark:text-gray-100 line-clamp-1">
                        {item.query_text}
                      </p>
                      <div className="flex justify-between items-center text-[11px] text-gray-500 font-mono pt-1 border-t border-gray-100 dark:border-gray-800">
                        <span>{item.total_duration_ms} ms</span>
                        <span>Conf: {item.confidence_score ? `${(item.confidence_score * 100).toFixed(0)}%` : 'N/A'}</span>
                        <div className="flex items-center text-blue-600 dark:text-blue-400">
                          Inspect <ChevronRight className="h-3 w-3 ml-0.5" />
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </Card>

          {/* Inspected Trace Diagnostics Drawer / Panel */}
          <div className="lg:col-span-7">
            {!inspectedTrace ? (
              <Card className="p-12 text-center border-dashed border-2 border-gray-300 dark:border-gray-700 space-y-3">
                <Search className="h-12 w-12 text-gray-400 mx-auto opacity-50" />
                <h3 className="text-base font-semibold text-gray-700 dark:text-gray-300">
                  Select a Query Trace to Inspect
                </h3>
                <p className="text-sm text-gray-500 max-w-md mx-auto">
                  Click on any query execution log from the left pane to view its stage latency waterfall, candidate breakdowns, and confidence signals.
                </p>
              </Card>
            ) : isLoadingTrace ? (
              <Card className="p-12 text-center text-sm text-gray-500 animate-pulse">
                Loading deep-dive forensic diagnostics...
              </Card>
            ) : (
              <Card className="p-5 border-gray-200 dark:border-gray-800 space-y-6">
                <div className="flex justify-between items-start pb-4 border-b border-gray-200 dark:border-gray-700">
                  <div>
                    <div className="flex items-center gap-2">
                      {renderOutcomeBadge(inspectedTrace.record.outcome)}
                      <span className="text-xs font-mono text-gray-500">
                        ID: {inspectedTrace.record.correlation_id}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-gray-900 dark:text-white mt-2">
                      &ldquo;{inspectedTrace.record.query_text}&rdquo;
                    </h3>
                  </div>
                  <div className="text-right text-xs font-mono space-y-1">
                    <div>Duration: <span className="font-bold text-gray-900 dark:text-white">{inspectedTrace.record.total_duration_ms} ms</span></div>
                    <div>Reliability: <span className="font-bold text-emerald-600 dark:text-emerald-400">{inspectedTrace.record.reliability_score?.toFixed(1)}</span></div>
                  </div>
                </div>

                {renderTraceWaterfall(inspectedTrace)}
                <hr className="border-gray-200 dark:border-gray-700" />
                {renderConfidenceSignals(inspectedTrace)}
                <hr className="border-gray-200 dark:border-gray-700" />
                {renderRetrievalCandidates(inspectedTrace)}
                {inspectedTrace.self_corrections && inspectedTrace.self_corrections.length > 0 && (
                  <>
                    <hr className="border-gray-200 dark:border-gray-700" />
                    {renderSelfCorrections(inspectedTrace)}
                  </>
                )}
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
