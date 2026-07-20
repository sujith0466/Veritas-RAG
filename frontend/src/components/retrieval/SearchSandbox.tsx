import * as React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  Sparkles,
  Sliders,
  Clock,
  Database,
  FileText,
  GitMerge,
  Award,
  RefreshCw,
  AlertCircle,
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/common/Card'
import { Badge } from '@/components/common/Badge'
import { Button } from '@/components/common/Button'
import { Input } from '@/components/common/Input'
import { cn } from '@/utils/cn'
import type {
  SearchSandboxRequest,
  SearchSandboxResponseDTO,
} from './types'

// Mock fallback sandbox response so developers can test UI immediately or when offline
const MOCK_SANDBOX_RESPONSE: SearchSandboxResponseDTO = {
  query_text: 'What are the strict multi-tenant TLS mutual authentication policies?',
  tenant_id: 'org_enterprise_demo',
  correlation_id: 'corr_sandbox_demo_8821',
  dense_results: [
    {
      chunk_id: 'chk-891a-1102',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'All inter-service gRPC and REST communications must enforce Mutual TLS (mTLS) with strict client certificate validation against the enterprise root CA authority.',
      score: 0.8842,
      source: 'dense',
      rank: 1,
    },
    {
      chunk_id: 'chk-332b-9941',
      document_id: 'doc-network-spec',
      document_version_id: 'ver-v1.1',
      tenant_id: 'org_enterprise_demo',
      content:
        'Network ingress gateways terminate TLS 1.3 traffic using ephemeral elliptic-curve Diffie-Hellman cipher suites with strict certificate transparency logging.',
      score: 0.8315,
      source: 'dense',
      rank: 2,
    },
  ],
  sparse_results: [
    {
      chunk_id: 'chk-114c-5509',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'Policy Section 4.2: TLS mutual authentication policies require annual rotation of cryptographic keys and zero-trust verification of tenant metadata claims.',
      score: 14.82,
      source: 'sparse',
      rank: 1,
    },
    {
      chunk_id: 'chk-891a-1102',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'All inter-service gRPC and REST communications must enforce Mutual TLS (mTLS) with strict client certificate validation against the enterprise root CA authority.',
      score: 12.35,
      source: 'sparse',
      rank: 2,
    },
  ],
  rrf_merged_results: [
    {
      chunk_id: 'chk-891a-1102',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'All inter-service gRPC and REST communications must enforce Mutual TLS (mTLS) with strict client certificate validation against the enterprise root CA authority.',
      score: 0.0322,
      source: 'rrf',
      rank: 1,
    },
    {
      chunk_id: 'chk-114c-5509',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'Policy Section 4.2: TLS mutual authentication policies require annual rotation of cryptographic keys and zero-trust verification of tenant metadata claims.',
      score: 0.0164,
      source: 'rrf',
      rank: 2,
    },
  ],
  final_reranked_results: [
    {
      chunk_id: 'chk-114c-5509',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'Policy Section 4.2: TLS mutual authentication policies require annual rotation of cryptographic keys and zero-trust verification of tenant metadata claims.',
      rrf_score: 0.0164,
      rerank_score: 0.965,
      final_rank: 1,
    },
    {
      chunk_id: 'chk-891a-1102',
      document_id: 'doc-sec-tls-01',
      document_version_id: 'ver-v2.4',
      tenant_id: 'org_enterprise_demo',
      content:
        'All inter-service gRPC and REST communications must enforce Mutual TLS (mTLS) with strict client certificate validation against the enterprise root CA authority.',
      rrf_score: 0.0322,
      rerank_score: 0.941,
      final_rank: 2,
    },
  ],
  stage_latencies: {
    dense_ms: 18.4,
    sparse_ms: 11.2,
    rrf_fusion_ms: 3.1,
    rerank_ms: 34.5,
    total_ms: 67.2,
  },
}

export interface SearchSandboxProps {
  className?: string
}

export function SearchSandbox({ className }: SearchSandboxProps = {}) {
  const [params, setParams] = React.useState<SearchSandboxRequest>({
    query: 'What are the strict multi-tenant TLS mutual authentication policies?',
    top_k: 5,
    rrf_k: 60,
    dedup_threshold: 0.92,
    limit_dense: 30,
    limit_sparse: 30,
  })

  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [response, setResponse] = React.useState<SearchSandboxResponseDTO>(MOCK_SANDBOX_RESPONSE)
  const [showControls, setShowControls] = React.useState(true)

  const handleExecuteSearch = async () => {
    if (!params.query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/v1/retrieval/sandbox', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': 'org_enterprise_demo',
        },
        body: JSON.stringify({
          query: params.query,
          top_k: params.top_k,
          rrf_k: params.rrf_k,
          dedup_threshold: params.dedup_threshold,
          limit_dense: params.limit_dense,
          limit_sparse: params.limit_sparse,
        }),
      })

      if (res.ok) {
        const payload = await res.json()
        setResponse(payload.data || MOCK_SANDBOX_RESPONSE)
      } else {
        setError('Backend returned non-200 status. Displaying interactive sandbox demo response.')
        setResponse({
          ...MOCK_SANDBOX_RESPONSE,
          query_text: params.query,
        })
      }
    } catch (err) {
      setError('Backend unreachable. Displaying interactive sandbox demo response.')
      setResponse({
        ...MOCK_SANDBOX_RESPONSE,
        query_text: params.query,
      })
    } finally {
      setLoading(false)
    }
  }

  const { stage_latencies } = response
  const total = stage_latencies.total_ms || 1

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header Banner */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary animate-pulse" />
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              Hybrid Retrieval Sandbox
            </h1>
            <Badge variant="subtle" className="ml-2">
              Phase 2 Milestone 4
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Compare multi-stage retrieval pipelines side-by-side: Dense HNSW, Lexical BM25, RRF Fusion, and Cross-Encoder Reranking.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => setShowControls(!showControls)}
          className="flex items-center gap-2 self-start md:self-auto"
        >
          <Sliders className="h-4 w-4" />
          {showControls ? 'Hide Parameters' : 'Tune Parameters'}
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 text-xs bg-warning/10 border border-warning/30 rounded-lg text-warning font-medium">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Interactive Controls & Parameter Tuning Panel */}
      <AnimatePresence>
        {showControls && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <Card className="border-border/80 bg-surface/50 backdrop-blur-md">
              <CardContent className="p-6 space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
                  <div className="md:col-span-9 relative">
                    <Search className="absolute left-3.5 top-3.5 h-5 w-5 text-muted-foreground" />
                    <Input
                      value={params.query}
                      onChange={(e) => setParams({ ...params, query: e.target.value })}
                      onKeyDown={(e) => e.key === 'Enter' && handleExecuteSearch()}
                      placeholder="Enter query to evaluate across multi-stage hybrid index..."
                      className="pl-11 pr-4 py-2.5 text-base w-full rounded-lg bg-background/80"
                    />
                  </div>
                  <div className="md:col-span-3 flex justify-end">
                    <Button
                      onClick={handleExecuteSearch}
                      disabled={loading}
                      className="w-full md:w-auto flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg shadow-md hover:shadow-primary/20 transition-all"
                    >
                      {loading ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Sparkles className="h-4 w-4" />
                      )}
                      Execute Hybrid Query
                    </Button>
                  </div>
                </div>

                {/* Slider Tuning Row */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 pt-3 border-t border-border/60">
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium text-muted-foreground">
                      <span>Final Top-K Output</span>
                      <span className="text-primary font-semibold">{params.top_k}</span>
                    </div>
                    <input
                      type="range"
                      min={1}
                      max={20}
                      value={params.top_k}
                      onChange={(e) => setParams({ ...params, top_k: Number(e.target.value) })}
                      className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium text-muted-foreground">
                      <span>RRF Constant (k)</span>
                      <span className="text-primary font-semibold">{params.rrf_k}</span>
                    </div>
                    <input
                      type="range"
                      min={10}
                      max={100}
                      step={5}
                      value={params.rrf_k}
                      onChange={(e) => setParams({ ...params, rrf_k: Number(e.target.value) })}
                      className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs font-medium text-muted-foreground">
                      <span>Jaccard Dedup Threshold</span>
                      <span className="text-primary font-semibold">{params.dedup_threshold}</span>
                    </div>
                    <input
                      type="range"
                      min={0.7}
                      max={1.0}
                      step={0.01}
                      value={params.dedup_threshold}
                      onChange={(e) =>
                        setParams({ ...params, dedup_threshold: Number(e.target.value) })
                      }
                      className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stage Breakdown Latency Bar */}
      <Card className="border-border/60 bg-muted/20">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 font-medium text-muted-foreground">
              <Clock className="h-4 w-4 text-primary" />
              <span>Pipeline Execution Breakdown</span>
              <span className="text-foreground font-semibold">({stage_latencies.total_ms} ms)</span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
                Dense: <strong className="text-foreground">{stage_latencies.dense_ms}ms</strong>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                Sparse: <strong className="text-foreground">{stage_latencies.sparse_ms}ms</strong>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                RRF: <strong className="text-foreground">{stage_latencies.rrf_fusion_ms}ms</strong>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-purple-500" />
                Rerank: <strong className="text-foreground">{stage_latencies.rerank_ms}ms</strong>
              </span>
            </div>
          </div>
          {/* Visual Progress Pill Bar */}
          <div className="w-full h-2 rounded-full bg-muted mt-3 flex overflow-hidden">
            <div
              style={{ width: `${(stage_latencies.dense_ms / total) * 100}%` }}
              className="bg-blue-500 h-full transition-all duration-300"
              title={`Dense: ${stage_latencies.dense_ms}ms`}
            />
            <div
              style={{ width: `${(stage_latencies.sparse_ms / total) * 100}%` }}
              className="bg-emerald-500 h-full transition-all duration-300"
              title={`Sparse: ${stage_latencies.sparse_ms}ms`}
            />
            <div
              style={{ width: `${(stage_latencies.rrf_fusion_ms / total) * 100}%` }}
              className="bg-amber-500 h-full transition-all duration-300"
              title={`RRF: ${stage_latencies.rrf_fusion_ms}ms`}
            />
            <div
              style={{ width: `${(stage_latencies.rerank_ms / total) * 100}%` }}
              className="bg-purple-500 h-full transition-all duration-300"
              title={`Rerank: ${stage_latencies.rerank_ms}ms`}
            />
          </div>
        </CardContent>
      </Card>

      {/* Side-by-Side 4-Column Multi-Stage Comparison Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Stage 1: Dense Vector Results */}
        <Card className="flex flex-col border-border/80 bg-surface/30">
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-blue-500" />
                <CardTitle className="text-sm font-semibold">Dense Vector</CardTitle>
              </div>
              <Badge variant="secondary" className="text-[10px]">
                {response.dense_results.length} found
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Semantic HNSW dot/cosine similarity
            </CardDescription>
          </CardHeader>
          <CardContent className="p-3 space-y-3 overflow-y-auto max-h-[500px]">
            {response.dense_results.map((item, idx) => (
              <motion.div
                key={item.chunk_id || idx}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg border border-border/60 bg-background/60 text-xs space-y-2 hover:border-blue-500/40 transition-all"
              >
                <div className="flex items-center justify-between font-mono">
                  <span className="text-muted-foreground">#{item.rank}</span>
                  <span className="text-blue-500 font-semibold">
                    {(item.score * 100).toFixed(1)}%
                  </span>
                </div>
                <p className="text-foreground/90 line-clamp-4 leading-relaxed">{item.content}</p>
                <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-between pt-1 border-t border-border/40">
                  <span>Doc: {item.document_id.slice(0, 8)}</span>
                  <span>{item.chunk_id.slice(0, 8)}</span>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        {/* Stage 2: Sparse Keyword Results */}
        <Card className="flex flex-col border-border/80 bg-surface/30">
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-emerald-500" />
                <CardTitle className="text-sm font-semibold">Sparse Lexical</CardTitle>
              </div>
              <Badge variant="secondary" className="text-[10px]">
                {response.sparse_results.length} found
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Exact keyword BM25 frequency score
            </CardDescription>
          </CardHeader>
          <CardContent className="p-3 space-y-3 overflow-y-auto max-h-[500px]">
            {response.sparse_results.map((item, idx) => (
              <motion.div
                key={item.chunk_id || idx}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg border border-border/60 bg-background/60 text-xs space-y-2 hover:border-emerald-500/40 transition-all"
              >
                <div className="flex items-center justify-between font-mono">
                  <span className="text-muted-foreground">#{item.rank}</span>
                  <span className="text-emerald-500 font-semibold">{item.score.toFixed(2)}</span>
                </div>
                <p className="text-foreground/90 line-clamp-4 leading-relaxed">{item.content}</p>
                <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-between pt-1 border-t border-border/40">
                  <span>Doc: {item.document_id.slice(0, 8)}</span>
                  <span>{item.chunk_id.slice(0, 8)}</span>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        {/* Stage 3: RRF Merged & Deduped Results */}
        <Card className="flex flex-col border-border/80 bg-surface/30">
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <GitMerge className="h-4 w-4 text-amber-500" />
                <CardTitle className="text-sm font-semibold">RRF Merged</CardTitle>
              </div>
              <Badge variant="secondary" className="text-[10px]">
                {response.rrf_merged_results.length} unique
              </Badge>
            </div>
            <CardDescription className="text-xs">
              Reciprocal Rank Fusion + Jaccard Dedup
            </CardDescription>
          </CardHeader>
          <CardContent className="p-3 space-y-3 overflow-y-auto max-h-[500px]">
            {response.rrf_merged_results.map((item, idx) => (
              <motion.div
                key={item.chunk_id || idx}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg border border-border/60 bg-background/60 text-xs space-y-2 hover:border-amber-500/40 transition-all"
              >
                <div className="flex items-center justify-between font-mono">
                  <span className="text-muted-foreground">#{item.rank}</span>
                  <span className="text-amber-500 font-semibold">
                    RRF: {item.score.toFixed(4)}
                  </span>
                </div>
                <p className="text-foreground/90 line-clamp-4 leading-relaxed">{item.content}</p>
                <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-between pt-1 border-t border-border/40">
                  <span>Doc: {item.document_id.slice(0, 8)}</span>
                  <span>{item.chunk_id.slice(0, 8)}</span>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>

        {/* Stage 4: Cross-Encoder Reranked Results (Final Output) */}
        <Card className="flex flex-col border-primary/40 bg-primary/5 shadow-md">
          <CardHeader className="pb-3 border-b border-primary/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Award className="h-4 w-4 text-purple-500" />
                <CardTitle className="text-sm font-semibold text-foreground">
                  Final Reranked
                </CardTitle>
              </div>
              <Badge variant="default" className="text-[10px] bg-purple-600 hover:bg-purple-700">
                Top {response.final_reranked_results.length}
              </Badge>
            </div>
            <CardDescription className="text-xs text-muted-foreground">
              Cross-encoder deep context scoring
            </CardDescription>
          </CardHeader>
          <CardContent className="p-3 space-y-3 overflow-y-auto max-h-[500px]">
            {response.final_reranked_results.map((item, idx) => (
              <motion.div
                key={item.chunk_id || idx}
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
                className="p-3 rounded-lg border border-purple-500/30 bg-background/90 text-xs space-y-2 shadow-sm hover:border-purple-500 transition-all"
              >
                <div className="flex items-center justify-between font-mono">
                  <span className="flex items-center gap-1 font-bold text-foreground">
                    #{item.final_rank}
                  </span>
                  <span className="text-purple-500 font-bold">
                    {(item.rerank_score * 100).toFixed(1)}% match
                  </span>
                </div>
                <p className="text-foreground font-medium leading-relaxed">{item.content}</p>
                <div className="text-[10px] text-muted-foreground font-mono flex items-center justify-between pt-1 border-t border-border/40">
                  <span>Doc: {item.document_id.slice(0, 8)}</span>
                  <span className="text-purple-400">RRF: {item.rrf_score.toFixed(4)}</span>
                </div>
              </motion.div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
