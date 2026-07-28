import { Database, Search, ShieldCheck, Building2, CheckCircle2 } from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { GlassCard } from '@/components/landing/GlassCard'
import { Stagger } from '@/components/motion/Stagger'
import { FadeUp } from '@/components/motion/FadeUp'

const FEATURE_CATEGORIES = [
  {
    title: 'Knowledge Intelligence',
    icon: Database,
    description: 'Transform raw data into structured, retrievable knowledge graphs.',
    features: ['Document Processing', 'Intelligent Chunking', 'Metadata Extraction', 'Enterprise Connectors']
  },
  {
    title: 'Retrieval Intelligence',
    icon: Search,
    description: 'Find the exact context needed using advanced hybrid search techniques.',
    features: ['Hybrid Search (Sparse + Dense)', 'Query Rewriting', 'Cross-Encoder Re-ranking', 'Reflection Engine']
  },
  {
    title: 'AI Reliability',
    icon: ShieldCheck,
    description: 'Ensure every response is accurate, safe, and fully explainable.',
    features: ['Grounded Responses', 'Source Attribution', 'Reliability Scoring', 'Hallucination Detection']
  },
  {
    title: 'Enterprise Platform',
    icon: Building2,
    description: 'Secure, scalable infrastructure built for enterprise compliance.',
    features: ['Granular RBAC', 'Multi-Tenant Architecture', 'Comprehensive Audit Logs', 'Headless API Integration']
  }
]

export function CoreFeatures() {
  return (
    <section id="features" className="py-24 bg-surface/30">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <FadeUp>
          <SectionHeading
            title="The Complete RAG Infrastructure."
            subtitle="Everything you need to build, deploy, and scale highly reliable AI applications in one unified platform."
            className="mb-16"
          />
        </FadeUp>

        <Stagger className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8" staggerDelay={0.1}>
          {FEATURE_CATEGORIES.map((category) => (
            <FadeUp key={category.title} yOffset={20}>
              <GlassCard padding="lg" interactive className="h-full flex flex-col bg-surface/50 backdrop-blur-xl border-white/10 shadow-glass">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-6 text-primary">
                  <category.icon className="w-6 h-6" />
                </div>
                
                <h3 className="text-xl font-bold text-foreground mb-3">{category.title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed mb-8 flex-1">
                  {category.description}
                </p>
                
                <ul className="space-y-3">
                  {category.features.map((feature) => (
                    <li key={feature} className="flex items-start space-x-2 text-sm text-foreground font-medium">
                      <CheckCircle2 className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>
              </GlassCard>
            </FadeUp>
          ))}
        </Stagger>
      </div>
    </section>
  )
}
