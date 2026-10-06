import {
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
  RotateCcw,
  Search,
  BookOpen,
  TrendingUp,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function ReliabilityEnginePage() {
  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-surface/80 backdrop-blur-md p-6 shadow-xl relative overflow-hidden">
      <div className="flex items-center justify-between pb-4 border-b border-border/50 mb-4">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold text-foreground">Self-Correction Orchestration</span>
        </div>
        <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-success/10 border border-success/20 text-success text-[11px] font-mono font-medium">
          <span>Reliability: 96.8%</span>
        </div>
      </div>

      {/* Self-Correction Loop Visual */}
      <div className="space-y-3">
        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <Search className="w-4 h-4 text-primary" />
            <span className="text-xs font-medium text-foreground">1. Retrieval Quality Audit</span>
          </div>
          <span className="text-[10px] font-mono text-success font-semibold">Pass (0.89)</span>
        </div>

        <div className="p-3 rounded-xl border border-border/50 bg-background/50 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <BookOpen className="w-4 h-4 text-info" />
            <span className="text-xs font-medium text-foreground">2. Citation Extraction & Mapping</span>
          </div>
          <span className="text-[10px] font-mono text-info font-semibold">6 Citations</span>
        </div>

        <div className="p-3 rounded-xl border border-warning/30 bg-warning/5 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <AlertTriangle className="w-4 h-4 text-warning" />
            <span className="text-xs font-medium text-foreground">3. Hallucination Guard Check</span>
          </div>
          <span className="text-[10px] font-mono text-warning font-semibold">Ambiguity Flagged</span>
        </div>

        <div className="p-3 rounded-xl border border-primary/40 bg-primary/10 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <RotateCcw className="w-4 h-4 text-primary animate-spin" style={{ animationDuration: '4s' }} />
            <span className="text-xs font-semibold text-primary">4. Autonomous Reflection Rewrite</span>
          </div>
          <span className="text-[10px] font-mono text-primary font-bold">Self-Corrected</span>
        </div>
      </div>
    </div>
  )

  const reliabilityMetrics = [
    {
      title: 'Context Grounding Score',
      score: '98.2%',
      desc: 'Mathematical verification that every assertion in the response is explicitly substantiated by retrieved chunks.',
    },
    {
      title: 'Citation Precision Rate',
      score: '99.4%',
      desc: 'Zero orphaned or fabricated citations. Every bracketed citation links directly to verified source passage coordinates.',
    },
    {
      title: 'Hallucination Mitigation',
      score: '99.9%',
      desc: 'Autonomous reflection loops rewrite ungrounded assertions before responses are streamed to end users.',
    },
    {
      title: 'Knowledge Absence Honesty',
      score: '100%',
      desc: 'When knowledge is genuinely missing from your documents, Veritas RAG admits knowledge absence instead of hallucinating plausible falsehoods.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Autonomous Reliability Engine"
        title={
          <>
            Hallucination-Resistant AI with{' '}
            <span className="text-primary">Autonomous Reflection Loops.</span>
          </>
        }
        subtitle="Veritas RAG continuously grades retrieval quality, validates generated claims against source passages, and triggers reflection loops when grounding falls below threshold."
        secondaryCtaText="See Security Architecture"
        secondaryCtaLink="/platform/security"
        visual={heroVisual}
      />

      {/* Metrics Section */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>Verifiable Scientific Metrics</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Mathematical Rigor Applied to LLM Generation
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Generic LLM wrappers trust the model to summarize accurately. Veritas RAG treats every LLM generation as untrusted output until mathematically verified against retrieved ground truth.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" staggerDelay={0.08}>
            {reliabilityMetrics.map((m) => (
              <FadeUp key={m.title} className="p-6 rounded-2xl border border-border/60 bg-surface/70 shadow-sm" yOffset={20}>
                <p className="text-4xl font-bold text-primary mb-2">{m.score}</p>
                <h3 className="text-base font-semibold text-foreground mb-2">{m.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">{m.desc}</p>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      {/* Side-by-Side Comparison: Ungrounded vs Grounded */}
      <section className="py-20 bg-surface/20 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="max-w-2xl mb-12" yOffset={20}>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
              Ungrounded LLM Output vs. Veritas Verified Response
            </h2>
            <p className="text-muted-foreground mt-3">
              Compare how standard foundation models handle domain queries versus Veritas RAG's grounded citation loop.
            </p>
          </FadeUp>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Standard Ungrounded */}
            <div className="p-6 md:p-8 rounded-2xl border border-danger/30 bg-danger/[0.02] relative">
              <div className="flex items-center justify-between pb-4 border-b border-danger/20 mb-4">
                <span className="text-xs font-semibold text-danger flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4" />
                  <span>Standard LLM / Naive RAG</span>
                </span>
                <span className="text-[11px] font-mono text-danger bg-danger/10 px-2 py-0.5 rounded-full">
                  Unverified / Hallucination Risk
                </span>
              </div>
              <p className="text-sm text-foreground/80 leading-relaxed mb-4">
                &quot;The contractual liability cap under the 2024 Master Agreement is set at $15,000,000 for gross negligence, and disputes must be arbitrated under Delaware law with a 30-day notice window.&quot;
              </p>
              <div className="p-3 rounded-xl bg-danger/10 border border-danger/20 text-xs text-danger space-y-1">
                <p className="font-semibold">Detected Defects:</p>
                <p>&bull; $15,000,000 figure was fabricated from a different clause</p>
                <p>&bull; Delaware jurisdiction contradicted by actual agreement (Texas law)</p>
                <p>&bull; Zero passage coordinates or page numbers provided</p>
              </div>
            </div>

            {/* Veritas Grounded */}
            <div className="p-6 md:p-8 rounded-2xl border border-success/30 bg-success/[0.02] relative">
              <div className="flex items-center justify-between pb-4 border-b border-success/20 mb-4">
                <span className="text-xs font-semibold text-success flex items-center gap-1.5">
                  <CheckCircle className="w-4 h-4" />
                  <span>Veritas RAG Reliability Engine</span>
                </span>
                <span className="text-[11px] font-mono text-success bg-success/10 px-2 py-0.5 rounded-full">
                  Grounded (98.4%)
                </span>
              </div>
              <p className="text-sm text-foreground leading-relaxed mb-4">
                &quot;Under Section 14.2 of the Master Agreement <span className="font-mono text-primary font-semibold">[Doc-4, p.19]</span>, aggregate liability for gross negligence is capped at 2x annual fees paid ($2,400,000) <span className="font-mono text-primary font-semibold">[Doc-4, p.21]</span>. Governing jurisdiction is Texas State Court <span className="font-mono text-primary font-semibold">[Doc-4, p.24]</span>.&quot;
              </p>
              <div className="p-3 rounded-xl bg-success/10 border border-success/20 text-xs text-success space-y-1">
                <p className="font-semibold">Verified Guarantees:</p>
                <p>&bull; Every figure explicitly linked to exact document chunk coordinates</p>
                <p>&bull; Reflection loop discarded ambiguous draft before streaming output</p>
                <p>&bull; Clickable citation coordinates enable instant legal audit</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready for Zero Hallucination Risk?"
        description="Deploy our autonomous reflection loop and start generating verifiable, explainable AI responses today."
      />
    </div>
  )
}
