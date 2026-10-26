import { useState } from 'react'
import { CheckCircle2, XCircle, Sparkles, AlertTriangle } from 'lucide-react'
import { motion, useReducedMotion, type Variants } from 'framer-motion'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { cn } from '@/utils/cn'

interface ComparisonRow {
  id: string
  category: string
  traditional: {
    title: string
    description: string
  }
  raguard: {
    title: string
    description: string
    highlight: string
  }
}

const COMPARISON_DATA: ComparisonRow[] = [
  {
    id: 'retrieval',
    category: 'Search & Context',
    traditional: {
      title: 'Basic Retrieval',
      description: 'Single-source dense vector search susceptible to semantic drift and lost keyword precision.',
    },
    raguard: {
      title: 'Hybrid Retrieval',
      description: 'Fused dense embeddings and sparse BM25 with reciprocal rank fusion for high-precision recall.',
      highlight: 'Dense + BM25 Fusion',
    },
  },
  {
    id: 'generation',
    category: 'Response Accuracy',
    traditional: {
      title: 'Generic Responses',
      description: 'Unchecked language generation prone to hallucinations, tone drift, and ungrounded fabrications.',
    },
    raguard: {
      title: 'Grounded Responses',
      description: 'Token-level factual grounding guaranteed against retrieved context with active hallucination suppression.',
      highlight: 'Zero-Hallucination Guard',
    },
  },
  {
    id: 'attribution',
    category: 'Traceability',
    traditional: {
      title: 'Limited Explainability',
      description: 'Black-box answers with no traceable passage lineage or inspectable source citations.',
    },
    raguard: {
      title: 'Source Attribution',
      description: 'Granular passage-level citations with cryptographic chunk provenance and relevance scores.',
      highlight: 'Cryptographic Lineage',
    },
  },
  {
    id: 'pipeline',
    category: 'Execution Pipeline',
    traditional: {
      title: 'Static Pipelines',
      description: 'Rigid linear execution with no runtime fallback logic when retrieved context is irrelevant.',
    },
    raguard: {
      title: 'Reflection Engine',
      description: 'Self-correcting feedback loops with autonomous query reformulations and fallback circuits.',
      highlight: 'Self-Correcting Loops',
    },
  },
  {
    id: 'observability',
    category: 'Telemetry & Ops',
    traditional: {
      title: 'Minimal Monitoring',
      description: 'Blind inference calls without real-time faithfulness tracking or latency SLO visibility.',
    },
    raguard: {
      title: 'Reliability Dashboard',
      description: 'Real-time telemetry, faithfulness scoring, token budgets, and operational SLO tracking.',
      highlight: 'Live Telemetry & SLOs',
    },
  },
  {
    id: 'security',
    category: 'Governance & Access',
    traditional: {
      title: 'Basic Security',
      description: 'Single-tenant or shared-namespace storage with missing compliance audit trails.',
    },
    raguard: {
      title: 'Enterprise RBAC & Audit Logs',
      description: 'Multi-tenant isolation, cryptographic audit trails, role-based controls, and webhook security.',
      highlight: 'Strict Multi-Tenancy',
    },
  },
]

export function WhyRaguard() {
  const shouldReduceMotion = useReducedMotion()
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)

  // Card reveal variants
  const cardsContainerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: shouldReduceMotion ? 0 : 0.12,
        delayChildren: shouldReduceMotion ? 0 : 0.05,
      },
    },
  }

  const cardVariants: Variants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 16 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        type: 'spring' as const,
        stiffness: 280,
        damping: 24,
      },
    },
  }

  // Row list sequential reveal variants
  const rowListVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: shouldReduceMotion ? 0 : 0.035,
        delayChildren: shouldReduceMotion ? 0 : 0.08,
      },
    },
  }

  const rowItemVariants: Variants = {
    hidden: { opacity: 0, y: shouldReduceMotion ? 0 : 6 },
    show: {
      opacity: 1,
      y: 0,
      transition: {
        type: 'spring' as const,
        stiffness: 320,
        damping: 26,
      },
    },
  }

  return (
    <section className="py-20 sm:py-24 border-t border-border/80 relative overflow-hidden bg-background">
      {/* Restrained ambient background accents */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[520px] h-[280px] bg-primary/4 rounded-full blur-3xl pointer-events-none -z-0" />
      <div className="absolute bottom-8 right-8 w-[340px] h-[200px] bg-champagne/4 rounded-full blur-3xl pointer-events-none -z-0" />

      <div className="container mx-auto px-4 sm:px-6 md:px-8 max-w-5xl relative z-10">
        <FadeUp yOffset={16} duration={0.45}>
          <div className="text-center mb-10 sm:mb-12">
            <div className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-2xs font-mono font-semibold uppercase tracking-wider text-primary bg-primary/10 border border-primary/20 mb-3 shadow-xs">
              <Sparkles className="w-3 h-3 text-primary" />
              <span>The Reliability Advantage</span>
            </div>
            <SectionHeading
              title="Why Veritas RAG?"
              subtitle="Differentiate your infrastructure with enterprise-grade reliability."
              className="mb-0"
            />
          </div>
        </FadeUp>

        {/* Staggered Cards Container */}
        <motion.div
          variants={cardsContainerVariants}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: '-40px' }}
          className="grid md:grid-cols-2 gap-5 lg:gap-6 items-stretch"
        >

          {/* Traditional RAG Surface */}
          <motion.div
            variants={cardVariants}
            className="flex flex-col justify-between rounded-2xl border border-border/80 bg-surface/50 dark:bg-[#16181b]/70 backdrop-blur-sm p-5 sm:p-6 lg:p-7 shadow-sm transition-all duration-200"
          >
            <div>
              {/* Header */}
              <div className="pb-4 mb-4 border-b border-border/60">
                <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-2xs font-mono font-semibold uppercase tracking-wider bg-muted/80 text-muted-foreground border border-border/60">
                  <AlertTriangle className="w-3 h-3 text-amber-500/80" />
                  <span>Legacy Architecture</span>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-muted-foreground/90 mt-2 tracking-tight">
                  Traditional RAG
                </h3>
                <p className="text-xs text-muted-foreground/70 mt-1 leading-relaxed">
                  First-generation vector retrieval pipelines built on single-pass inference and unconstrained generation.
                </p>
              </div>

              {/* Rows with sequential reveal */}
              <motion.ul variants={rowListVariants} className="space-y-2.5 p-0 m-0">
                {COMPARISON_DATA.map((row, i) => {
                  const isHovered = hoveredIndex === i
                  return (
                    <motion.li
                      key={`trad-${row.id}`}
                      variants={rowItemVariants}
                      onMouseEnter={() => setHoveredIndex(i)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      className={cn(
                        'list-none px-3.5 py-2.5 rounded-xl border transition-all duration-150',
                        isHovered
                          ? 'bg-muted/50 border-muted-foreground/25 shadow-xs'
                          : 'bg-muted/20 border-transparent hover:border-border/60'
                      )}
                    >
                      <div className="flex items-start gap-2.5 sm:gap-3">
                        <div className="mt-0.5 p-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-500/70 shrink-0">
                          <XCircle className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-xs sm:text-sm text-muted-foreground/90 tracking-tight">
                              {row.traditional.title}
                            </span>
                            <span className="text-[10px] font-mono text-muted-foreground/50 uppercase tracking-wider">
                              {row.category}
                            </span>
                          </div>
                          <p className="text-[11px] sm:text-xs text-muted-foreground/70 mt-0.5 leading-relaxed">
                            {row.traditional.description}
                          </p>
                        </div>
                      </div>
                    </motion.li>
                  )
                })}
              </motion.ul>
            </div>

            <div className="pt-3.5 mt-4 border-t border-border/50 text-center">
              <span className="text-2xs font-mono text-muted-foreground/60 uppercase tracking-wider">
                Baseline Vector Ingestion Standard
              </span>
            </div>
          </motion.div>

          {/* Veritas RAG Flagship Elevated Surface */}
          <motion.div
            variants={cardVariants}
            className="relative flex flex-col justify-between rounded-2xl border-2 border-primary/30 dark:border-primary/40 hover:border-primary/45 bg-surface-elevated/95 dark:bg-[#1d2024]/95 backdrop-blur-md p-5 sm:p-6 lg:p-7 shadow-lg shadow-primary/5 transition-all duration-200"
          >
            {/* Subtle top brand illumination bar */}
            <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-primary via-champagne to-primary rounded-t-2xl opacity-90" />

            <div>
              {/* Header */}
              <div className="pb-4 mb-4 border-b border-border/70">
                <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-2xs font-mono font-semibold uppercase tracking-wider bg-primary/10 text-primary border border-primary/25 shadow-xs">
                  <span className="relative flex h-2 w-2 items-center justify-center">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                    <span className="absolute inset-0 rounded-full ring-1 ring-primary/40" />
                  </span>
                  <span>Enterprise Reliability Standard</span>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-foreground mt-2 tracking-tight flex items-center gap-2">
                  <span>Veritas RAG</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                  Self-correcting, verifiable knowledge platform designed for mission-critical enterprise workloads.
                </p>
              </div>

              {/* Rows with sequential reveal */}
              <motion.ul variants={rowListVariants} className="space-y-2.5 p-0 m-0">
                {COMPARISON_DATA.map((row, i) => {
                  const isHovered = hoveredIndex === i
                  return (
                    <motion.li
                      key={`raguard-${row.id}`}
                      variants={rowItemVariants}
                      onMouseEnter={() => setHoveredIndex(i)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      className={cn(
                        'list-none px-3.5 py-2.5 rounded-xl border transition-all duration-150',
                        isHovered
                          ? 'bg-primary/[0.08] border-primary/40 shadow-xs'
                          : 'bg-surface/60 dark:bg-card/40 border-border/60 hover:border-primary/25'
                      )}
                    >
                      <div className="flex items-start gap-2.5 sm:gap-3">
                        <div className="mt-0.5 p-1 rounded-full bg-primary/15 border border-primary/30 text-primary shadow-xs shrink-0">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2 flex-wrap sm:flex-nowrap">
                            <span className="font-semibold text-xs sm:text-sm text-foreground tracking-tight">
                              {row.raguard.title}
                            </span>
                            <span className="text-[9px] sm:text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 shrink-0">
                              {row.raguard.highlight}
                            </span>
                          </div>
                          <p className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 leading-relaxed">
                            {row.raguard.description}
                          </p>
                        </div>
                      </div>
                    </motion.li>
                  )
                })}
              </motion.ul>
            </div>

            <div className="pt-3.5 mt-4 border-t border-border/60 flex items-center justify-between text-xs">
              <span className="text-2xs font-mono text-primary font-semibold uppercase tracking-wider flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                Self-Correcting Architecture
              </span>
              <span className="text-2xs font-mono text-muted-foreground">
                100% Provenance & Attribution
              </span>
            </div>
          </motion.div>

        </motion.div>
      </div>
    </section>
  )
}
