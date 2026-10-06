import { useState, useMemo } from 'react'
import {
  Calendar,
  Clock,
  ArrowRight,
  Sparkles,
  BookOpen,
  CheckCircle2,
} from 'lucide-react'
import { motion } from 'framer-motion'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
} from '@/components/common/Dialog'
import { Button } from '@/components/common/Button'

interface ArticleSection {
  heading: string
  content: string[]
  callout?: string
}

interface BlogArticle {
  id: number
  title: string
  category: 'Architecture' | 'Research' | 'Engineering' | 'Security'
  date: string
  readTime: string
  excerpt: string
  author: string
  sections: ArticleSection[]
}

const BLOG_ARTICLES: BlogArticle[] = [
  {
    id: 1,
    title: 'Why Reciprocal Rank Fusion Outperforms Pure Vector Search in Production',
    category: 'Architecture',
    date: 'October 2026',
    readTime: '7 min read',
    author: 'Veritas Systems Architecture Team',
    excerpt:
      'Vector similarity excels at conceptual semantic matching, but frequently fails on exact alphanumeric part codes and statutory legal articles. Here is why dual-stream RRF is the new gold standard for enterprise retrieval.',
    sections: [
      {
        heading: 'The Limits of Pure Dense Semantic Retrieval',
        content: [
          'Dense vector representations project text into continuous embedding spaces where geometric proximity corresponds to semantic similarity. While this is exceptionally capable for conceptual analogies and natural language inquiries, production enterprise workloads frequently break pure vector retrieval.',
          'Specifically, exact alphanumeric identifiers, catalog numbers, financial line-item codes, and specific statutory sections often have negligible semantic variance in embedding space. A search for "Rule 10b-5(b)" may mistakenly retrieve general insider trading passages rather than the precise clause needed by legal analysts.',
        ],
        callout:
          'Dense embeddings maximize conceptual recall, but lack the precision required for deterministic compliance and exact-token verification.',
      },
      {
        heading: 'Dual-Stream Lexical and Vector Indexing',
        content: [
          'To overcome this limitation, Veritas RAG implements a parallel dual-stream retrieval pipeline. Every ingested document is indexed simultaneously into an inverted BM25 lexical index and a high-dimensional vector index backed by Qdrant.',
          'When a user or agent submits a query, it is dispatched concurrently across both retrieval engines. The BM25 stream captures exact token matches, acronyms, and alphanumeric identifiers, while the dense stream surfaces contextually relevant passages that express the same meaning using distinct vocabulary.',
        ],
      },
      {
        heading: 'The Mathematics of Reciprocal Rank Fusion (RRF)',
        content: [
          'The fundamental hurdle in combining sparse and dense retrieval is score comparability: BM25 returns unbounded term frequency scores, whereas cosine similarity produces bounded values between -1 and 1. Simple linear score combinations are brittle and require continuous manual tuning.',
          'Reciprocal Rank Fusion (RRF) resolves this by relying purely on positional rankings rather than raw scores. For each candidate document d across rankers M, the fused score is calculated as:',
          'RRF(d) = Σ [ 1 / (k + r_m(d)) ] where k is a smoothing constant (typically k = 60) and r_m(d) is the rank of document d in ranker m.',
          'This non-parametric formulation prevents either search mechanism from disproportionately biasing the result set, ensuring that documents appearing consistently high in either or both channels are prioritized.',
        ],
      },
      {
        heading: 'Grounding Implications & Production Impact',
        content: [
          'In extensive enterprise benchmarks across financial filings and engineering manuals, dual-stream RRF achieved a 28% increase in Top-3 retrieval recall compared to standalone dense search.',
          'Most importantly, by guaranteeing that exact definitions and references are present in the retrieved context window, downstream hallucination rates dropped to near zero, providing a verifiable foundation for LLM generation.',
        ],
      },
    ],
  },
  {
    id: 2,
    title: 'The Mathematics of Reliability: Quantifying Faithfulness & Citation Precision',
    category: 'Research',
    date: 'September 2026',
    readTime: '10 min read',
    author: 'AI Safety & Verification Research Group',
    excerpt:
      'How we formulated Veritas RAG’s 0–100% Reliability Score. A deep dive into context overlap algorithms, hallucination penalty matrices, and claim-level verification loops.',
    sections: [
      {
        heading: 'Why Traditional Confidence Scores Fail Enterprise Users',
        content: [
          'Standard softmax logits and raw token probabilities from large language models represent token predictability rather than factual accuracy. A model can generate an entirely fabricated statement with 99% token confidence.',
          'Enterprise decision-makers in legal, medical, and financial environments require an objective, deterministic reliability metric that guarantees assertions are provably grounded in retrieved corporate knowledge.',
        ],
        callout:
          'Token probability measures linguistic likelihood; reliability scoring measures mathematical adherence to source evidence.',
      },
      {
        heading: 'The Three Pillars of the Veritas Reliability Score',
        content: [
          'Veritas RAG computes a composite 0–100% Reliability Score formulated from three independent mathematical pillars:',
          '1. Faithfulness Score (Sf): The proportion of statements in the generated response that can be mathematically deduced or directly substantiated by retrieved source passages.',
          '2. Context Relevancy (Sr): The ratio of signal-to-noise within retrieved context, penalizing irrelevant chunks that increase cognitive load on the LLM.',
          '3. Citation Precision (Sc): The exactness with which inline citation markers point to the precise bounding boxes, paragraph offsets, and page coordinates containing the supporting fact.',
        ],
      },
      {
        heading: 'Atomic Claim Extraction and Verification Loops',
        content: [
          'To calculate Faithfulness, the Veritas Reliability Engine breaks down the assistant output into atomic propositional claims. Each claim is converted into a structured verification query and evaluated against the retrieved context vector space.',
          'If a claim introduces external entities, ungrounded dates, or uncorroborated numerical values, the system applies an exponential penalty matrix to the composite score.',
        ],
      },
      {
        heading: 'Deterministic Thresholds and Automated Escalation',
        content: [
          'Responses scoring above 90% are certified as High Confidence and served immediately to the user. Responses between 75% and 89% trigger citation warnings, while outputs falling below 75% are intercepted by autonomous reflection loops for immediate regeneration.',
        ],
      },
    ],
  },
  {
    id: 3,
    title: 'Designing Multi-Tenant Vector Partitioning with Qdrant and PostgreSQL',
    category: 'Engineering',
    date: 'August 2026',
    readTime: '8 min read',
    author: 'Infrastructure & Data Platform Engineering',
    excerpt:
      'Enforcing complete tenant isolation across millions of vector points without sacrificing query throughput. We examine collection naming, filter pushdown, and resource contention trade-offs.',
    sections: [
      {
        heading: 'The Enterprise Multi-Tenancy Conundrum',
        content: [
          'In multi-tenant SaaS environments, enterprise clients demand complete cryptographic and physical data isolation. A single accidental vector leak between tenant organizations represents an existential security incident.',
          'However, spinning up dedicated vector database clusters per tenant is economically unsustainable and creates severe operational fragmentation at scale.',
        ],
      },
      {
        heading: 'Partitioning Strategy in Veritas RAG',
        content: [
          'Veritas RAG employs a hybrid partitioning model combining workspace-isolated collections in Qdrant with tenant payload tagging for defense-in-depth.',
          'Every workspace receives a dedicated collection name formatted as raguard_knowledge_{tenant_id}. Furthermore, all indexed points carry immutable tenant_id metadata payloads, enabling low-level payload filter pushdown at the HNSW index layer.',
        ],
        callout:
          'Double-barrier isolation: dedicated collection namespaces paired with cryptographic payload filter enforcement guarantee zero cross-tenant contamination.',
      },
      {
        heading: 'Atomic Relational Synchronization with PostgreSQL',
        content: [
          'Document versions, upload metadata, chunk boundaries, and RBAC permissions reside in PostgreSQL. To ensure transactional consistency across relational and vector stores, we utilize an outbox event pattern.',
          'When a document is deleted or modified in PostgreSQL, synchronization workers atomically purge or re-index the corresponding vector points in Qdrant before confirming the operation to the client.',
        ],
      },
      {
        heading: 'Throughput Optimization & Connection Pooling',
        content: [
          'By leveraging PgBouncer connection pooling and persistent HTTP/2 keep-alive connections to Qdrant, Veritas RAG sustains over 1,200 concurrent retrieval queries per second while maintaining sub-250ms P99 search latencies.',
        ],
      },
    ],
  },
  {
    id: 4,
    title: 'Preventing LLM Hallucinations Through Autonomous Reflection Loops',
    category: 'Research',
    date: 'July 2026',
    readTime: '6 min read',
    author: 'Cognitive Architecture & RAG Research',
    excerpt:
      'Instead of streaming raw LLM drafts directly to end users, our reliability engine grades intermediate outputs and automatically triggers corrective reflection rewrites when grounding fails.',
    sections: [
      {
        heading: 'The Hazard of Unvalidated First-Token Streaming',
        content: [
          'Modern conversational AI interfaces prioritize immediate Time-To-First-Token (TTFT) by piping LLM output directly to WebSocket or Server-Sent Events (SSE) connections. While this feels responsive, it delivers hallucinated statements to the end user before any safety validation can occur.',
          'Once a false assertion has been rendered on screen, retracting it damages user confidence and enterprise trust.',
        ],
      },
      {
        heading: 'The Veritas Autonomous Reflection Architecture',
        content: [
          'Veritas RAG introduces an intermediate reflection controller between the generation model and the client streaming buffer. In high-stakes enterprise mode, initial drafts are evaluated against retrieved document chunks.',
          'The reflection model specifically inspects entity relationships, numeric quantities, and causal claims. If any component lacks strict evidentiary support, the reflection loop intervenes.',
        ],
        callout:
          'Self-correction occurs in memory before final delivery, turning speculative drafts into validated, audit-ready intelligence.',
      },
      {
        heading: 'Targeted Retrieval Expansion and Self-Correction',
        content: [
          'When an ungrounded claim is detected, the engine does not merely prompt the LLM to "try again." Instead, it performs diagnostic analysis to identify the exact informational deficit.',
          'It then generates targeted sub-queries, executes secondary retrieval across the tenant knowledge base, and provides the missing evidence to the generation model for a guided rewrite.',
        ],
      },
      {
        heading: 'Performance Balancing & Sub-Second Latency',
        content: [
          'Through speculative decoding and parallel verification worker threads, Veritas RAG completes reflection loops in under 800 milliseconds, preserving real-time conversational fluidity while guaranteeing 100% evidentiary grounding.',
        ],
      },
    ],
  },
  {
    id: 5,
    title: 'Zero-Downtime Knowledge Ingestion with Asynchronous Celery Workers',
    category: 'Engineering',
    date: 'June 2026',
    readTime: '5 min read',
    author: 'Distributed Systems & Data Pipeline Team',
    excerpt:
      'A practical breakdown of handling multi-gigabyte document batches with Redis message brokers, preflight chunk validation, and atomic Qdrant index updates.',
    sections: [
      {
        heading: 'Decoupling Ingestion from Web Request Lifecycle',
        content: [
          'Ingesting enterprise repositories containing thousands of PDF contracts, technical blueprints, and spreadsheet tables is computationally intensive. Executing OCR, table extraction, and chunking in synchronous HTTP threads leads to socket timeouts and gateway crashes.',
          'Veritas RAG decouples document ingestion completely using asynchronous task pipelines powered by Celery and Redis.',
        ],
      },
      {
        heading: 'The Multi-Stage Processing Pipeline',
        content: [
          'When an administrator uploads documents or registers a website crawl target, the ingestion pipeline executes through four strictly ordered phases:',
          '1. Storage Preflight Validation: Verifies file headers, MIME signatures, and storage quotas before allocating compute resources.',
          '2. Structural Text Extraction: Parses document hierarchies, preserves table column alignments, and extracts OCR layers.',
          '3. Semantic Boundary Chunking: Splits text along natural semantic breakpoints while maintaining sliding token overlaps.',
          '4. Vector Generation & Synchronization: Batch-embeds chunk vectors and executes upserts into tenant Qdrant collections.',
        ],
      },
      {
        heading: 'Backpressure Control and Worker Resilience',
        content: [
          'To prevent memory exhaustion during multi-gigabyte ingestion spikes, our Redis broker enforces concurrency limits and task acknowledgment guarantees. If a worker container crashes during processing, unacknowledged tasks are re-queued automatically without duplicate chunk generation.',
        ],
        callout:
          'Idempotent task design ensures that interrupted ingestion jobs resume precisely from the last successful chunk index.',
      },
    ],
  },
  {
    id: 6,
    title: 'Ephemeral Join Credentials: Modernizing Enterprise Workspace Onboarding',
    category: 'Security',
    date: 'May 2026',
    readTime: '6 min read',
    author: 'Identity & Access Management Team',
    excerpt:
      'Why permanent team invite links represent an enterprise security liability, and how we engineered cryptographically signed, self-expiring Join Codes with instant revocation.',
    sections: [
      {
        heading: 'The Security Vulnerability of Static Invitation Links',
        content: [
          'In many collaboration and SaaS platforms, workspace join links remain valid indefinitely. These URLs inevitably leak into email threads, shared team documents, and chat channels.',
          'Months after a project completes, unauthorized individuals or departing employees can exploit static links to gain authenticated access to proprietary company repositories.',
        ],
      },
      {
        heading: 'Time-Bounded Ephemeral Join Codes',
        content: [
          'Veritas RAG eliminates static vulnerability by introducing cryptographically signed, ephemeral Join Credentials. Administrators configure explicit expiration horizons (24 hours, 7 days, 30 days, 60 days, or customized durations).',
          'Each code is linked to an HMAC signature verified on the server side against the workspace security state. Once expired, the code is immediately rejected by the onboarding gateway.',
        ],
        callout:
          'Ephemeral join codes minimize credential lifespan, cutting the exposure window from months to hours.',
      },
      {
        heading: 'Instant Revocation and Session Isolation',
        content: [
          'If a join credential is inadvertently posted to a public channel, administrators can trigger immediate revocation with a single click. The rotation generates a fresh credential while keeping all active member sessions uninterrupted.',
        ],
      },
      {
        heading: 'Strict Role-Based Access Control (RBAC)',
        content: [
          'Join codes strictly govern the entry role (Member or Viewer) and enforce tenant isolation barriers. Elevated roles (Owner, Admin) can never be assigned via join codes, eliminating privilege escalation vectors.',
        ],
      },
    ],
  },
]

const CATEGORIES = ['All', 'Architecture', 'Research', 'Engineering', 'Security'] as const

export function BlogPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>('All')
  const [activeArticle, setActiveArticle] = useState<BlogArticle | null>(null)

  // Derive visible articles cleanly from the immutable source dataset
  const filteredArticles = useMemo(() => {
    if (selectedCategory === 'All') {
      return BLOG_ARTICLES
    }
    return BLOG_ARTICLES.filter(
      (a) => a.category.toLowerCase() === selectedCategory.toLowerCase(),
    )
  }, [selectedCategory])

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
            {CATEGORIES.map((cat) => {
              const isActive = selectedCategory.toLowerCase() === cat.toLowerCase()
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-4 py-2 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'bg-surface border border-border/60 text-muted-foreground hover:text-foreground hover:bg-surface-elevated'
                  }`}
                >
                  {cat}
                </button>
              )
            })}
          </div>

          {/* Articles Grid: keyed by category so re-renders cleanly mount every time */}
          <motion.div
            key={selectedCategory}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8"
          >
            {filteredArticles.map((post) => (
              <div
                key={post.id}
                className="p-7 rounded-2xl border border-border/60 bg-surface/70 hover:bg-surface-elevated/90 transition-all duration-300 shadow-sm flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[11px] font-semibold text-primary px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20">
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
                  <button
                    type="button"
                    onClick={() => setActiveArticle(post)}
                    className="font-semibold text-primary flex items-center space-x-1 group-hover:underline cursor-pointer hover:text-primary/80 transition-colors"
                  >
                    <span>Read Article</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1 transition-transform group-hover:translate-x-1" />
                  </button>
                </div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Premium Article Reader Dialog */}
      <Dialog
        open={!!activeArticle}
        onOpenChange={(open) => {
          if (!open) setActiveArticle(null)
        }}
      >
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto p-6 sm:p-8 bg-surface-elevated border border-border/80 shadow-2xl rounded-2xl text-foreground">
          {activeArticle && (
            <div className="space-y-6">
              {/* Category & Read Time Meta */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-border/40">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
                  <Sparkles className="w-3 h-3" />
                  {activeArticle.category}
                </span>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{activeArticle.date}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{activeArticle.readTime}</span>
                  </div>
                </div>
              </div>

              {/* Title & Author */}
              <DialogHeader className="text-left space-y-2">
                <DialogTitle className="text-2xl sm:text-3xl font-bold text-foreground leading-tight tracking-tight">
                  {activeArticle.title}
                </DialogTitle>
                <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                  <span>Authored by {activeArticle.author}</span>
                </p>
              </DialogHeader>

              {/* Excerpt Lead */}
              <div className="p-4 rounded-xl bg-primary/5 border border-primary/20 text-sm text-foreground/90 font-medium leading-relaxed">
                {activeArticle.excerpt}
              </div>

              {/* Structured Article Body */}
              <div className="space-y-6 pt-2">
                {activeArticle.sections.map((section, idx) => (
                  <div key={idx} className="space-y-3">
                    <h4 className="text-lg font-bold text-foreground tracking-tight">
                      {section.heading}
                    </h4>
                    {section.content.map((paragraph, pIdx) => (
                      <p
                        key={pIdx}
                        className="text-sm sm:text-base text-muted-foreground leading-relaxed"
                      >
                        {paragraph}
                      </p>
                    ))}
                    {section.callout && (
                      <div className="my-4 p-4 rounded-xl bg-surface border-l-4 border-l-primary border-border/60 text-sm italic text-foreground/90">
                        "{section.callout}"
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Modal Footer with Close Button */}
              <div className="pt-6 border-t border-border/40 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <BookOpen className="w-3.5 h-3.5 text-primary" />
                  <span>Veritas RAG Engineering Publication Series</span>
                </div>
                <DialogClose asChild>
                  <Button
                    variant="outline"
                    className="rounded-full px-5 text-xs font-semibold"
                  >
                    Close Article
                  </Button>
                </DialogClose>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <MarketingCTA
        title="Stay Ahead in AI Reliability Engineering"
        description="Deploy Veritas RAG and experience state-of-the-art hybrid retrieval and autonomous grounding loops."
      />
    </div>
  )
}
