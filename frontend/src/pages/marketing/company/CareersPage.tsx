import { Heart } from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function CareersPage() {
  const engineeringFocus = [
    {
      title: 'Vector Retrieval & Index Systems',
      desc: 'Optimizing HNSW index parameters, quantization benchmarks, and sub-second recall across millions of dense embedding vectors in Qdrant.',
      tags: ['Vector DBs', 'Qdrant', 'RRF', 'Python / Rust'],
    },
    {
      title: 'Distributed Ingestion Pipelines',
      desc: 'Architecting resilient, asynchronous Celery task pipelines and Redis message workers handling multi-gigabyte document batches.',
      tags: ['Celery', 'Redis', 'PostgreSQL', 'FastAPI'],
    },
    {
      title: 'AI Reliability & Hallucination Guardrails',
      desc: 'Engineering autonomous reflection loops, cross-encoder rerankers, and mathematically verifiable grounding score algorithms.',
      tags: ['LLM Safety', 'Rerankers', 'Grounding', 'PyTorch'],
    },
    {
      title: 'Enterprise Frontend & Real-Time UX',
      desc: 'Crafting responsive, accessible React interfaces with Framer Motion animations, SSE streaming token assembly, and interactive dashboards.',
      tags: ['React', 'TypeScript', 'Tailwind CSS', 'SSE'],
    },
  ]

  const cultureValues = [
    {
      title: 'Engineering Craftsmanship',
      desc: 'We care deeply about clean architectures, defensive typing, comprehensive tests, and zero unverified shortcuts.',
    },
    {
      title: 'Scientific Honesty',
      desc: 'We measure ourselves by reproducible benchmarks, not marketing hype. If a retrieval strategy fails, we inspect why.',
    },
    {
      title: 'Customer Grounding',
      desc: 'We build for real users who depend on our system for high-stakes decisions in law, medicine, and finance.',
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Careers & Engineering Culture"
        title={
          <>
            Building the Infrastructure for{' '}
            <span className="text-primary">Trustworthy Enterprise AI.</span>
          </>
        }
        subtitle="Join our mission to eliminate hallucinations and build high-performance vector retrieval, autonomous self-correction, and enterprise multi-tenancy."
        secondaryCtaText="Contact Team"
        secondaryCtaLink="/contact"
      />

      {/* Culture Section */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Heart className="w-3.5 h-3.5" />
              <span>How We Work</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              A Culture of Systems Rigor
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              We are an engineering-driven team obsessed with eliminating model fabrication and scaling deterministic knowledge pipelines.
            </p>
          </FadeUp>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-24">
            {cultureValues.map((v) => (
              <div key={v.title} className="p-8 rounded-2xl border border-border/60 bg-surface/70 shadow-sm">
                <h3 className="text-lg font-bold text-foreground mb-3">{v.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{v.desc}</p>
              </div>
            ))}
          </div>

          {/* Focus Areas */}
          <div className="mb-12">
            <h3 className="text-2xl md:text-3xl font-bold text-foreground mb-4">
              Engineering Disciplines & Talent Registry
            </h3>
            <p className="text-muted-foreground max-w-2xl">
              We are always excited to connect with outstanding systems thinkers, researchers, and frontend craftsmen.
            </p>
          </div>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 gap-8" staggerDelay={0.08}>
            {engineeringFocus.map((f) => (
              <FadeUp key={f.title} className="p-8 rounded-2xl border border-border/60 bg-surface/70 flex flex-col justify-between shadow-sm" yOffset={20}>
                <div>
                  <h4 className="text-xl font-bold text-foreground mb-2">{f.title}</h4>
                  <p className="text-sm text-muted-foreground leading-relaxed mb-6">{f.desc}</p>
                </div>
                <div className="flex flex-wrap gap-2 pt-4 border-t border-border/40">
                  {f.tags.map((t) => (
                    <span key={t} className="text-xs font-mono px-2.5 py-1 rounded-md bg-surface-elevated border border-border/50 text-foreground/80">
                      {t}
                    </span>
                  ))}
                </div>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Interested in Joining Us?"
        description="Reach out to connect directly with our engineering founders about open opportunities."
      />
    </div>
  )
}
