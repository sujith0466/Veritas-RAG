import {
  Search,
  Zap,
  SlidersHorizontal,
  Network,
  Cpu,
  Target,
  CheckCircle2,
  GitMerge,
  Workflow,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function HybridRetrievalPage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <span className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Workflow className="w-3.5 h-3.5 text-primary" />
          <span>Dual-Stream Fusion Engine</span>
        </span>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
          RRF + Reranker Active
        </span>
      </div>

      {/* Query Bar */}
      <div className="p-2.5 rounded-xl border border-border/60 bg-background/80 flex items-center space-x-2 mb-4 text-xs font-mono text-foreground">
        <Search className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="truncate">&quot;Clause 14.2 indemnification cap under Texas law&quot;</span>
      </div>

      {/* Split Streams */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="p-3 rounded-xl border border-primary/30 bg-primary/5 flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-1.5 text-primary text-xs font-semibold mb-1">
              <Zap className="w-3.5 h-3.5" />
              <span>Dense Vector</span>
            </div>
            <p className="text-[11px] text-muted-foreground">Qdrant HNSW cosine embeddings</p>
          </div>
          <div className="mt-3 text-[10px] font-mono text-primary font-semibold">Semantic Match: 0.924</div>
        </div>

        <div className="p-3 rounded-xl border border-info/30 bg-info/5 flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-1.5 text-info text-xs font-semibold mb-1">
              <Search className="w-3.5 h-3.5" />
              <span>Sparse BM25</span>
            </div>
            <p className="text-[11px] text-muted-foreground">Exact token lexical scoring</p>
          </div>
          <div className="mt-3 text-[10px] font-mono text-info font-semibold">Exact Match: &quot;14.2&quot;, &quot;Texas&quot;</div>
        </div>
      </div>

      {/* Fusion & Rerank Layer */}
      <div className="p-3 rounded-xl border border-border/60 bg-surface-elevated/70 flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2.5">
          <GitMerge className="w-4 h-4 text-primary" />
          <div>
            <p className="text-xs font-semibold text-foreground">Reciprocal Rank Fusion (RRF)</p>
            <p className="text-[11px] text-muted-foreground">Mathematical rank normalization (k=60)</p>
          </div>
        </div>
        <span className="text-[10px] font-mono font-medium text-foreground">Merged 40 &rarr; 10</span>
      </div>

      <div className="p-3 rounded-xl border border-success/30 bg-success/5 flex items-center justify-between">
        <div className="flex items-center space-x-2.5">
          <Cpu className="w-4 h-4 text-success" />
          <div>
            <p className="text-xs font-semibold text-foreground">Cross-Encoder Reranker</p>
            <p className="text-[11px] text-muted-foreground">Full attention re-scoring for top-5 chunks</p>
          </div>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/20 text-success font-semibold">
          Final Top-K Ready
        </span>
      </div>
    </div>
  )

  const searchCapabilities = [
    {
      icon: Search,
      title: 'Dense Semantic Vector Search',
      description: 'Navigates high-dimensional semantic vector spaces using Qdrant HNSW indices to understand complex user intent and synonyms.',
    },
    {
      icon: Zap,
      title: 'BM25 Lexical Keyword Search',
      description: 'Guarantees zero missed recalls on exact part codes, invoice IDs, acronyms, and statutory legal clause references.',
    },
    {
      icon: GitMerge,
      title: 'Reciprocal Rank Fusion (RRF)',
      description: 'Merges sparse and dense search results without fragile score weighting using mathematically robust reciprocal rank normalization.',
    },
    {
      icon: Cpu,
      title: 'Cross-Encoder Precision Reranker',
      description: 'Re-evaluates top candidates using deep cross-attention, eliminating false positives before context is assembled for LLM generation.',
    },
    {
      icon: Target,
      title: 'Retrieval Quality Assessment',
      description: 'Calculates precision and relevance scores in real-time. If quality falls below threshold, automated query rewrites are triggered.',
    },
    {
      icon: SlidersHorizontal,
      title: 'Dynamic Tenant Partition Filtering',
      description: 'Executes metadata filters directly at the Qdrant query planner level, guaranteeing complete multi-tenant boundary compliance.',
    },
  ]

  const comparisonRows = [
    {
      feature: 'Handles exact part numbers & codes',
      keyword: 'Excellent',
      vector: 'Poor (semantic drift)',
      veritas: '100% Precision (BM25 stream)',
    },
    {
      feature: 'Captures conceptual intent & synonyms',
      keyword: 'Fails without keyword overlap',
      vector: 'Excellent',
      veritas: 'Excellent (Qdrant Dense stream)',
    },
    {
      feature: 'Resistance to false-positive retrieval',
      keyword: 'Moderate',
      vector: 'Moderate',
      veritas: 'Superior (Cross-Encoder reranking)',
    },
    {
      feature: 'Score calibration across modalities',
      keyword: 'Uncalibrated raw scores',
      vector: 'Cosine distance only',
      veritas: 'Mathematically normalized via RRF',
    },
    {
      feature: 'Latency SLA for Enterprise Workloads',
      keyword: '< 50ms',
      vector: '< 60ms',
      veritas: '< 120ms total end-to-end',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Dual-Stream Hybrid Retrieval"
        title={
          <>
            Precision at Scale with{' '}
            <span className="text-primary">Reciprocal Rank Fusion & Reranking.</span>
          </>
        }
        subtitle="Combining the exact-match precision of BM25 lexical search with the semantic depth of dense embeddings, re-scored by a cross-encoder model."
        secondaryCtaText="Explore Architecture"
        secondaryCtaLink="/platform/reliability-engine"
        visual={heroVisual}
      />

      {/* Architecture Highlights */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Network className="w-3.5 h-3.5" />
              <span>Multi-Stage Retrieval Architecture</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Why Pure Vector Search Is Not Enough
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Pure vector embeddings excel at general concept matching, but fail on statutory legal codes, part IDs, and numbers. Veritas RAG unifies the best of lexical and semantic intelligence.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" staggerDelay={0.08}>
            {searchCapabilities.map((cap) => (
              <FadeUp key={cap.title} className="p-6 rounded-2xl border border-border/60 bg-surface/60 hover:bg-surface-elevated/80 transition-all duration-300 shadow-sm" yOffset={20}>
                <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-5">
                  <cap.icon className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">{cap.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{cap.description}</p>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="py-20 bg-surface/20 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="max-w-2xl mb-12" yOffset={20}>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
              Retrieval Architecture Comparison
            </h2>
            <p className="text-muted-foreground mt-3">
              See how Veritas RAG's dual-stream hybrid fusion compares to legacy keyword search and standalone vector databases.
            </p>
          </FadeUp>

          <div className="overflow-x-auto rounded-2xl border border-border/60 bg-surface/70 shadow-sm">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-surface-elevated/50 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <th className="py-4 px-6">Capability</th>
                  <th className="py-4 px-6">Pure Keyword (BM25)</th>
                  <th className="py-4 px-6">Pure Vector (Dense)</th>
                  <th className="py-4 px-6 text-primary">Veritas Hybrid (RRF + Rerank)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {comparisonRows.map((row) => (
                  <tr key={row.feature} className="hover:bg-surface-elevated/30 transition-colors">
                    <td className="py-4 px-6 font-medium text-foreground">{row.feature}</td>
                    <td className="py-4 px-6 text-muted-foreground">{row.keyword}</td>
                    <td className="py-4 px-6 text-muted-foreground">{row.vector}</td>
                    <td className="py-4 px-6 font-semibold text-primary flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0" />
                      <span>{row.veritas}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Elevate Retrieval Accuracy?"
        description="Experience Reciprocal Rank Fusion and Cross-Encoder reranking live on your documents."
      />
    </div>
  )
}
