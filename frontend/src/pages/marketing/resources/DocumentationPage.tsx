import { useState } from 'react'
import {
  BookOpen,
  Terminal,
  Code2,
  Cpu,
  Layers,
  Shield,
  Copy,
  Check,
  ArrowRight,
  Database,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

export function DocumentationPage() {
  const [copied, setCopied] = useState(false)

  const copyCode = () => {
    navigator.clipboard.writeText(`curl -X POST http://localhost:8000/api/v1/chat/sessions \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"title": "Regulatory Analysis", "workspace_id": "ws-prod-01"}'`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-[#0F172A] text-slate-100 p-6 shadow-2xl relative overflow-hidden font-mono text-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-4">
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 rounded-full bg-rose-500/80" />
          <div className="w-3 h-3 rounded-full bg-amber-500/80" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/80" />
        </div>
        <button
          onClick={copyCode}
          className="flex items-center space-x-1.5 text-slate-400 hover:text-slate-200 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
          <span className="text-[11px]">{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <div className="text-slate-300 leading-relaxed overflow-x-auto">
        <p className="text-emerald-400"># 1. Initialize a new grounded chat session</p>
        <p>curl -X POST http://localhost:8000/api/v1/chat/sessions \</p>
        <p className="pl-4">-H &quot;Authorization: Bearer $TOKEN&quot; \</p>
        <p className="pl-4">-H &quot;Content-Type: application/json&quot; \</p>
        <p className="pl-4">-d &apos;{JSON.stringify({ title: 'Audit Session', workspace_id: 'ws-prod-01' })}&apos;</p>
        <p className="text-slate-500 mt-2"># Response: 201 Created</p>
        <p className="text-amber-300">&#123;&quot;session_id&quot;: &quot;sess_948a2...&quot;, &quot;status&quot;: &quot;READY&quot;&#125;</p>
      </div>
    </div>
  )

  const docTracks = [
    {
      title: 'Quickstart & Installation',
      desc: 'Get Veritas RAG up and running in under 5 minutes using Docker Compose, PostgreSQL, Redis, and Qdrant.',
      icon: Terminal,
      topics: ['Docker Compose setup', 'Environment variables (.env)', 'Initial admin bootstrapping'],
    },
    {
      title: 'Knowledge Ingestion & Parsing',
      desc: 'Learn how to configure document extractors, custom chunking sizes, and asynchronous Celery workers.',
      icon: Layers,
      topics: ['Supported file formats', 'Chunk overlap tuning', 'Vector sync triggers'],
    },
    {
      title: 'Hybrid Retrieval Tuning',
      desc: 'Optimize Reciprocal Rank Fusion parameters, BM25 tokenizer settings, and Cross-Encoder reranker thresholds.',
      icon: Cpu,
      topics: ['RRF k-constant calibration', 'Top-K chunk limits', 'Dense vs sparse weighting'],
    },
    {
      title: 'Reliability & Hallucination Guard',
      desc: 'Configure autonomous reflection loops, citation formatting, and grounding confidence cutoffs.',
      icon: Shield,
      topics: ['Reliability score formulas', 'Automated query rewriting', 'Citation extraction format'],
    },
    {
      title: 'Multi-Tenant Security Architecture',
      desc: 'Enforce tenant isolation, ephemeral Join Codes, and granular RBAC across organization workspaces.',
      icon: Database,
      topics: ['Join code expiration lifecycle', 'Qdrant collection partitioning', 'Audit log delivery'],
    },
    {
      title: 'SSE Real-Time Streaming SDK',
      desc: 'Integrate live streaming tokens, inline citation markers, and reliability badges into your React or Node app.',
      icon: Code2,
      topics: ['EventSource API usage', 'Token chunk assembly', 'Error recovery on stream disconnect'],
    },
  ]

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="Developer & Architecture Documentation"
        title={
          <>
            Build, Integrate, and Scale{' '}
            <span className="text-primary">Grounded AI Systems.</span>
          </>
        }
        subtitle="Complete architectural blueprints, configuration guides, and API integration tutorials for deploying Veritas RAG in your enterprise infrastructure."
        secondaryCtaText="Browse API Reference"
        secondaryCtaLink="/resources/api-reference"
        visual={heroVisual}
      />

      {/* Documentation Tracks */}
      <section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="text-center max-w-3xl mx-auto mb-16" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <BookOpen className="w-3.5 h-3.5" />
              <span>Structured Developer Guides</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Everything You Need to Deploy Production RAG
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-4">
              Explore step-by-step guides covering deployment, retrieval tuning, reliability guardrails, and tenant security.
            </p>
          </FadeUp>

          <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8" staggerDelay={0.08}>
            {docTracks.map((track) => (
              <FadeUp key={track.title} className="p-7 rounded-2xl border border-border/60 bg-surface/70 hover:bg-surface-elevated/80 transition-all shadow-sm flex flex-col justify-between" yOffset={20}>
                <div>
                  <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-5">
                    <track.icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-lg font-bold text-foreground mb-2">{track.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed mb-6">{track.desc}</p>
                </div>
                <div className="pt-4 border-t border-border/40 space-y-2">
                  {track.topics.map((t) => (
                    <div key={t} className="flex items-center space-x-2 text-xs text-muted-foreground">
                      <ArrowRight className="w-3 h-3 text-primary flex-shrink-0" />
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Build with Veritas RAG?"
        description="Launch your local development workspace or explore the full REST API reference documentation."
      />
    </div>
  )
}
