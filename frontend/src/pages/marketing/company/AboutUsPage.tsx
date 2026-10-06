import {
  Shield,
  Target,
  Lock,
  Cpu,
  Compass,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function AboutUsPage() {
  const principles = [
    {
      icon: Shield,
      title: 'Grounding Before Generation',
      desc: 'Generative models without verified source grounding are liabilities in production. We treat every assertion as untrusted until proven against indexed ground truth.',
    },
    {
      icon: Target,
      title: 'Zero Fabrication Tolerance',
      desc: 'When knowledge is genuinely missing from a corpus, admitting absence is far safer than generating a plausible fabrication. Honesty is engineered into our core loop.',
    },
    {
      icon: Lock,
      title: 'Architectural Multi-Tenancy',
      desc: 'Security cannot depend on LLM system prompt instructions. In Veritas RAG, multi-tenancy is enforced at the database query and vector collection layer.',
    },
    {
      icon: Cpu,
      title: 'Transparency & Explainability',
      desc: 'Every answer must be auditable. From reciprocal rank fusion scores to character-level passage coordinates, we make every step observable.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Our Mission & Philosophy"
        title={
          <>
            Engineered for Truth in an Era of{' '}
            <span className="text-primary">Generative AI.</span>
          </>
        }
        subtitle="Veritas RAG was created on a single conviction: enterprise AI must be explainable, mathematically auditable, and strictly grounded in private truth."
        secondaryCtaText="Explore Platform"
        secondaryCtaLink="/platform/reliability-engine"
      />

      {/* Mission Statement */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <div className="max-w-3xl mx-auto text-center mb-20">
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground mb-6">
              The Problem with Naive RAG
            </h2>
            <p className="text-lg text-muted-foreground leading-relaxed">
              Standard retrieval-augmented generation prototypes work well in demos, but fail when deployed in high-stakes environments. Vector drift leads to irrelevant chunks, models hallucinate unsupported conclusions, and lack of multi-tenant isolation creates dangerous compliance exposures.
            </p>
            <p className="text-lg text-muted-foreground leading-relaxed mt-4">
              Veritas RAG replaces guesswork with mathematical certainty. By unifying BM25 lexical search, dense vector embeddings, reciprocal rank fusion, and autonomous reflection loops, we deliver enterprise AI you can genuinely trust.
            </p>
          </div>

          {/* Principles Grid */}
          <div className="mb-12 text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-3">
              <Compass className="w-3.5 h-3.5" />
              <span>Core Engineering Principles</span>
            </div>
            <h3 className="text-2xl md:text-3xl font-bold text-foreground">What Guides Our Engineering</h3>
          </div>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 gap-8" staggerDelay={0.08}>
            {principles.map((p) => (
              <FadeUp key={p.title} className="p-8 rounded-2xl border border-border/60 bg-surface/70 shadow-sm" yOffset={20}>
                <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-6">
                  <p.icon className="w-6 h-6" />
                </div>
                <h4 className="text-xl font-bold text-foreground mb-3">{p.title}</h4>
                <p className="text-muted-foreground leading-relaxed text-sm">{p.desc}</p>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Build With Us?"
        description="Experience verifiable, hallucination-resistant knowledge intelligence across your enterprise."
      />
    </div>
  )
}
