import { useState } from 'react'
import {
  Calendar,
  Clock,
  ArrowRight,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function BlogPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>('All')

  const articles = [
    {
      id: 1,
      title: 'Why Reciprocal Rank Fusion Outperforms Pure Vector Search in Production',
      category: 'Architecture',
      date: 'October 2026',
      readTime: '7 min read',
      excerpt: 'Vector similarity excels at conceptual semantic matching, but frequently fails on exact alphanumeric part codes and statutory legal articles. Here is why dual-stream RRF is the new gold standard for enterprise retrieval.',
    },
    {
      id: 2,
      title: 'The Mathematics of Reliability: Quantifying Faithfulness & Citation Precision',
      category: 'Research',
      date: 'September 2026',
      readTime: '10 min read',
      excerpt: 'How we formulated Veritas RAG’s 0–100% Reliability Score. A deep dive into context overlap algorithms, hallucination penalty matrices, and claim-level verification loops.',
    },
    {
      id: 3,
      title: 'Designing Multi-Tenant Vector Partitioning with Qdrant and PostgreSQL',
      category: 'Engineering',
      date: 'August 2026',
      readTime: '8 min read',
      excerpt: 'Enforcing complete tenant isolation across millions of vector points without sacrificing query throughput. We examine collection naming, filter pushdown, and resource contention trade-offs.',
    },
    {
      id: 4,
      title: 'Preventing LLM Hallucinations Through Autonomous Reflection Loops',
      category: 'Research',
      date: 'July 2026',
      readTime: '6 min read',
      excerpt: 'Instead of streaming raw LLM drafts directly to end users, our reliability engine grades intermediate outputs and automatically triggers corrective reflection rewrites when grounding fails.',
    },
    {
      id: 5,
      title: 'Zero-Downtime Knowledge Ingestion with Asynchronous Celery Workers',
      category: 'Engineering',
      date: 'June 2026',
      readTime: '5 min read',
      excerpt: 'A practical breakdown of handling multi-gigabyte document batches with Redis message brokers, preflight chunk validation, and atomic Qdrant index updates.',
    },
    {
      id: 6,
      title: 'Ephemeral Join Credentials: Modernizing Enterprise Workspace Onboarding',
      category: 'Security',
      date: 'May 2026',
      readTime: '6 min read',
      excerpt: 'Why permanent team invite links represent an enterprise security liability, and how we engineered cryptographically signed, self-expiring Join Codes with instant revocation.',
    },
  ]

  const categories = ['All', 'Architecture', 'Research', 'Engineering', 'Security']

  const filtered = selectedCategory === 'All'
    ? articles
    : articles.filter((a) => a.category === selectedCategory)

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Research & Engineering Publications"
        title={
          <>
            Insights on RAG Reliability,{' '}
            <span className="text-primary">Grounding & Vector Systems.</span>
          </>
        }
        subtitle="Technical deep-dives, architectural benchmarks, and distributed systems engineering from the team building Veritas RAG."
        secondaryCtaText="Explore Documentation"
        secondaryCtaLink="/resources/documentation"
      />

      {/* Articles Section */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          {/* Category Filter Chips */}
          <div className="flex flex-wrap items-center gap-2 mb-12">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-4 py-2 rounded-full text-xs font-semibold transition-all ${
                  selectedCategory === cat
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'bg-surface border border-border/60 text-muted-foreground hover:text-foreground hover:bg-surface-elevated'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Articles Grid */}
          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8" staggerDelay={0.08}>
            {filtered.map((post) => (
              <FadeUp key={post.id} className="p-7 rounded-2xl border border-border/60 bg-surface/70 hover:bg-surface-elevated/90 transition-all duration-300 shadow-sm flex flex-col justify-between" yOffset={20}>
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[11px] font-semibold text-primary px-2.5 py-0.5 rounded-full bg-primary/10">
                      {post.category}
                    </span>
                    <div className="flex items-center space-x-1 text-xs text-muted-foreground">
                      <Clock className="w-3.5 h-3.5" />
                      <span>{post.readTime}</span>
                    </div>
                  </div>
                  <h3 className="text-xl font-bold text-foreground mb-3 leading-snug">
                    {post.title}
                  </h3>
                  <p className="text-sm text-muted-foreground leading-relaxed mb-6">
                    {post.excerpt}
                  </p>
                </div>

                <div className="pt-4 border-t border-border/40 flex items-center justify-between text-xs text-muted-foreground">
                  <div className="flex items-center space-x-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{post.date}</span>
                  </div>
                  <span className="font-semibold text-primary flex items-center space-x-1 group">
                    <span>Read Article</span>
                    <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </div>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Stay Ahead in AI Reliability Engineering"
        description="Deploy Veritas RAG and experience state-of-the-art hybrid retrieval and autonomous grounding loops."
      />
    </div>
  )
}
