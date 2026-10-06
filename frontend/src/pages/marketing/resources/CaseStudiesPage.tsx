import {
  Briefcase,
  TrendingUp,
  Scale,
  Cpu,
  CheckCircle2,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function CaseStudiesPage() {
  const casePatterns = [
    {
      title: 'Global Investment Firm: 10-K & Footnote Synthesis',
      industry: 'Financial Services',
      challenge: 'Analysts spent 30+ hours per week manually extracting liability covenants and EBITDA adjustments across thousands of regulatory 10-K filings. Naive LLM solutions frequently hallucinated financial figures.',
      solution: 'Deployed Veritas RAG with hierarchical table parsing, Reciprocal Rank Fusion, and strict numeric passage grounding with page coordinates.',
      results: [
        '99.4% verifiable citation accuracy on numeric disclosures',
        '70% reduction in preliminary filing review turnaround',
        'Complete tenant isolation between private equity deal rooms',
      ],
      icon: TrendingUp,
    },
    {
      title: 'Corporate Legal Department: Multi-Party Contract Review',
      industry: 'Legal Tech & Compliance',
      challenge: 'In-house counsel needed to compare non-standard indemnity clauses across legacy acquisitions without risking cross-client or cross-matter confidentiality leaks.',
      solution: 'Implemented Veritas RAG’s semantic clause chunking, Cross-Encoder reranking, and tenant-partitioned Qdrant vector collections.',
      results: [
        'Instant side-by-side clause comparison with exact paragraph citation',
        'Zero cross-matter data contamination enforced at vector layer',
        'Autonomous reflection loops eliminated fabricated legal case citations',
      ],
      icon: Scale,
    },
    {
      title: 'Infrastructure Engineering Org: Distributed RFC Intelligence',
      industry: 'Enterprise Software & DevOps',
      challenge: 'Over 15,000 internal engineering RFCs, system architectural diagrams, and incident post-mortems were scattered across internal wikis, leading to duplicate work and conflicting design patterns.',
      solution: 'Integrated Veritas RAG’s real-time Markdown and URL ingestion with hybrid BM25 + dense vector search to answer system architecture inquiries.',
      results: [
        'Sub-850ms retrieval latency across 15,000+ technical documents',
        'Engineers receive exact diagram coordinates and RFC links in replies',
        'Automated fallback flags undocumented APIs rather than inventing specs',
      ],
      icon: Cpu,
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Enterprise Deployment Patterns"
        title={
          <>
            Architectural Proof Points in{' '}
            <span className="text-primary">Enterprise Production.</span>
          </>
        }
        subtitle="Explore real architectural patterns and verified deployment outcomes across financial analysis, legal compliance, and engineering knowledge systems."
        secondaryCtaText="Review Platform Features"
        secondaryCtaLink="/platform/reliability-engine"
      />

      {/* Case Patterns Grid */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Briefcase className="w-3.5 h-3.5" />
              <span>Proven Deployment Architectures</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Production Workloads Built on Trust
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Learn how mission-critical teams eliminate generative hallucinations by deploying Veritas RAG's deterministic grounding and multi-tenant isolation.
            </p>
          </FadeUp>

          <Stagger className="space-y-8" staggerDelay={0.1}>
            {casePatterns.map((cp) => (
              <FadeUp key={cp.title} className="p-8 md:p-10 rounded-3xl border border-border/60 bg-surface/70 shadow-sm" yOffset={20}>
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6 pb-6 border-b border-border/40 mb-6">
                  <div>
                    <span className="text-xs font-semibold text-primary px-3 py-1 rounded-full bg-primary/10 inline-block mb-3">
                      {cp.industry}
                    </span>
                    <h3 className="text-2xl font-bold text-foreground">{cp.title}</h3>
                  </div>
                  <div className="w-12 h-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
                    <cp.icon className="w-6 h-6" />
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-8 mb-8">
                  <div>
                    <h4 className="text-xs uppercase tracking-wider font-bold text-muted-foreground mb-2">The Challenge</h4>
                    <p className="text-sm text-foreground/80 leading-relaxed">{cp.challenge}</p>
                  </div>
                  <div>
                    <h4 className="text-xs uppercase tracking-wider font-bold text-muted-foreground mb-2">The Veritas Architecture</h4>
                    <p className="text-sm text-foreground/80 leading-relaxed">{cp.solution}</p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-surface-elevated/60 border border-border/50">
                  <h4 className="text-xs uppercase tracking-wider font-bold text-primary mb-3">Verified Operational Outcomes</h4>
                  <div className="grid md:grid-cols-3 gap-4">
                    {cp.results.map((res) => (
                      <div key={res} className="flex items-start space-x-2 text-xs text-foreground/90">
                        <CheckCircle2 className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                        <span>{res}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Build Your Own Success Story?"
        description="Deploy Veritas RAG and see how verifiable knowledge intelligence transforms your team's workflow."
      />
    </div>
  )
}
