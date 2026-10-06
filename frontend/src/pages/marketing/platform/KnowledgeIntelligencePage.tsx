import { motion } from 'framer-motion'
import {
  FileText,
  Layers,
  Database,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  Search,
  Activity,
  Workflow,
  CheckCircle2,
  FileCheck2,
  RefreshCw,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function KnowledgeIntelligencePage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-danger/60" />
          <div className="w-3 h-3 rounded-full bg-warning/60" />
          <div className="w-3 h-3 rounded-full bg-success/60" />
        </div>
        <div className="text-xs font-mono text-muted-foreground flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-primary animate-pulse" />
          <span>Ingestion & Chunk Pipeline</span>
        </div>
      </div>

      {/* Visual Pipeline Stages */}
      <div className="space-y-3">
        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Multi-Source Ingestion</p>
              <p className="text-[11px] text-muted-foreground">PDF, Markdown, Web URLs, DOCX</p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">Parsed</span>
        </div>

        <div className="flex justify-center -my-1 text-muted-foreground/60">
          <ArrowRight className="w-4 h-4 rotate-90" />
        </div>

        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-info/10 text-info flex items-center justify-center">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Adaptive Chunking</p>
              <p className="text-[11px] text-muted-foreground">Semantic boundary + Overlap preservation</p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-info/10 text-info font-medium">512 Tokens</span>
        </div>

        <div className="flex justify-center -my-1 text-muted-foreground/60">
          <ArrowRight className="w-4 h-4 rotate-90" />
        </div>

        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-success/10 text-success flex items-center justify-center">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-semibold text-foreground">Vector Sync to Qdrant</p>
              <p className="text-[11px] text-muted-foreground">Tenant-isolated collection indexing</p>
            </div>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-success/10 text-success font-medium">Indexed</span>
        </div>
      </div>
    </div>
  )

  const capabilities = [
    {
      icon: FileCheck2,
      title: 'Deterministic Document Parsing',
      description: 'Preserves tables, headings, footnotes, and document hierarchy without losing structural context during ingestion.',
    },
    {
      icon: Layers,
      title: 'Multi-Strategy Chunking',
      description: 'Select between fixed-window, paragraph-aware, and semantic sentence boundaries tailored to your content domain.',
    },
    {
      icon: RefreshCw,
      title: 'Real-Time Vector Synchronization',
      description: 'Asynchronous Celery pipelines guarantee that newly uploaded or modified documents are indexed immediately into Qdrant.',
    },
    {
      icon: ShieldCheck,
      title: 'Granular Tenant Isolation',
      description: 'Every workspace maintains dedicated vector collections with cryptographic partition keys to prevent cross-tenant data leakage.',
    },
    {
      icon: Search,
      title: 'Provenance & Lineage Tracking',
      description: 'Every chunk retains its content hash, document version, page coordinates, and parent hierarchy for 100% auditability.',
    },
    {
      icon: Workflow,
      title: 'Automated Pipeline Health',
      description: 'Continuous monitoring of chunk quality, orphaned vectors, and token budget metrics across your enterprise knowledge base.',
    },
  ]

  const chunkingStrategies = [
    {
      name: 'Semantic Boundary Chunking',
      badge: 'Recommended for Research & Technical Docs',
      desc: 'Splits on natural topic transitions using semantic sentence embeddings while ensuring zero mid-thought cutoff.',
      benefits: ['Preserves complete arguments', 'Maximizes embedding coherence', 'Eliminates orphaned clauses'],
    },
    {
      name: 'Fixed Window with Overlap',
      badge: 'High-Throughput General Corpus',
      desc: 'Deterministic token sizing with customizable 10–25% overlap to ensure context is never split across retrieval boundaries.',
      benefits: ['Predictable token distribution', 'Optimal for dense search', 'Configurable overlap sliding'],
    },
    {
      name: 'Hierarchical Section Chunking',
      badge: 'Contracts & Structured Filings',
      desc: 'Respects legal articles, sections, and nested lists to guarantee child chunks reference parent document coordinates.',
      benefits: ['Contract clause integrity', 'Exact footnote preservation', 'Direct citation coordinate mapping'],
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Enterprise Knowledge Intelligence"
        title={
          <>
            Turn Disparate Enterprise Data into{' '}
            <span className="text-primary">Verifiable Ground Truth.</span>
          </>
        }
        subtitle="High-fidelity document parsing, multi-strategy chunking, and deterministic vector synchronization across your organization's unstructured content."
        secondaryCtaText="Explore Documentation"
        secondaryCtaLink="/resources/documentation"
        visual={heroVisual}
      />

      {/* Metrics Bar */}
      <section className="py-12 border-y border-border/40 bg-surface/30 backdrop-blur-sm">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <p className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">100%</p>
              <p className="text-sm text-muted-foreground mt-1">Provenance Lineage</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">&lt; 850ms</p>
              <p className="text-sm text-muted-foreground mt-1">Chunk Sync Latency</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">0</p>
              <p className="text-sm text-muted-foreground mt-1">Cross-Tenant Leakage</p>
            </div>
            <div>
              <p className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">4</p>
              <p className="text-sm text-muted-foreground mt-1">Adaptive Chunk Strategies</p>
            </div>
          </div>
        </div>
      </section>

      {/* Core Capabilities */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Engineered for Precision</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Intelligent Ingestion Built for Enterprise Scale
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Raw text ingestion fails when layout structure matters. Veritas RAG preserves document semantics through specialized pipeline layers.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" staggerDelay={0.08}>
            {capabilities.map((cap) => (
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

      {/* Chunking Strategies Deep-Dive */}
      <section className="py-20 bg-surface/20 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="max-w-2xl mb-12" yOffset={20}>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
              Adaptive Chunking for Every Content Type
            </h2>
            <p className="text-muted-foreground mt-3">
              One size does not fit all. Select optimal strategies depending on whether you are parsing dense financial statements, code repositories, or legal covenants.
            </p>
          </FadeUp>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {chunkingStrategies.map((strat, i) => (
              <motion.div
                key={strat.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-7 rounded-2xl border border-border/60 bg-surface/80 flex flex-col justify-between shadow-sm"
              >
                <div>
                  <span className="text-[11px] font-semibold text-primary px-2.5 py-1 rounded-full bg-primary/10 inline-block mb-4">
                    {strat.badge}
                  </span>
                  <h3 className="text-xl font-bold text-foreground mb-3">{strat.name}</h3>
                  <p className="text-sm text-muted-foreground mb-6 leading-relaxed">{strat.desc}</p>
                </div>
                <div className="pt-4 border-t border-border/40 space-y-2">
                  {strat.benefits.map((b) => (
                    <div key={b} className="flex items-center space-x-2 text-xs text-foreground/80">
                      <CheckCircle2 className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                      <span>{b}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Ingest Your Enterprise Knowledge?"
        description="Experience deterministic parsing, adaptive chunking, and tenant-isolated vector indexing on your private infrastructure."
      />
    </div>
  )
}
