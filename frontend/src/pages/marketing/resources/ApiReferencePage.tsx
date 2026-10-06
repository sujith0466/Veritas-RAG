import { useState } from 'react'
import {
  Code2,
  Check,
  Copy,
  Radio,
} from 'lucide-react'
import { MarketingHero } from '../components/MarketingHero'
import { MarketingCTA } from '../components/MarketingCTA'
import { FadeUp } from '@/components/motion/FadeUp'

export function ApiReferencePage() {
  const [activeEndpoint, setActiveEndpoint] = useState<string>('stream')
  const [copied, setCopied] = useState(false)

  const endpoints = [
    {
      id: 'stream',
      method: 'POST',
      path: '/api/v1/chat/sessions/{id}/stream',
      tag: 'Chat & Streaming',
      desc: 'Streams grounded LLM tokens, inline citation events, and real-time reliability confidence scores using Server-Sent Events (SSE).',
      curl: `curl -N -X POST http://localhost:8000/api/v1/chat/sessions/sess_123/stream \\
  -H "Authorization: Bearer $JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "What is the liability cap under Section 14?"}'`,
      response: `event: token
data: {"content": "Under Section 14.2 of the agreement, "}

event: token
data: {"content": "liability is capped at 2x annual fees [1]."}

event: citation
data: {"id": 1, "doc_id": "doc_99", "page": 19, "passage": "liability shall not exceed..."}

event: done
data: {"reliability_score": 0.984, "grounded": true}`,
    },
    {
      id: 'ingest',
      method: 'POST',
      path: '/api/v1/documents',
      tag: 'Documents',
      desc: 'Uploads and enqueues documents for asynchronous multi-strategy chunking, embedding generation, and Qdrant vector indexing.',
      curl: `curl -X POST http://localhost:8000/api/v1/documents \\
  -H "Authorization: Bearer $JWT_TOKEN" \\
  -F "file=@annual_report_2024.pdf" \\
  -F "chunk_strategy=semantic"`,
      response: `{
  "document_id": "doc_4819a",
  "status": "PROCESSING",
  "filename": "annual_report_2024.pdf",
  "chunk_strategy": "semantic",
  "created_at": "2026-10-06T18:00:00Z"
}`,
    },
    {
      id: 'vectors',
      method: 'GET',
      path: '/api/v1/vectors/health',
      tag: 'Vector DB',
      desc: 'Returns collection status, point counts, dimension configuration, and indexing health for the authenticated tenant.',
      curl: `curl -X GET http://localhost:8000/api/v1/vectors/health \\
  -H "Authorization: Bearer $JWT_TOKEN"`,
      response: `{
  "status": "HEALTHY",
  "tenant_collection": "raguard_knowledge_tenant_01",
  "vectors_count": 14280,
  "indexed_vectors_count": 14280,
  "distance": "Cosine",
  "dimension": 1536
}`,
    },
    {
      id: 'join',
      method: 'POST',
      path: '/api/v1/workspaces/join',
      tag: 'Workspaces',
      desc: 'Validates an ephemeral Join Code and grants role-based workspace membership without requiring manual email invitations.',
      curl: `curl -X POST http://localhost:8000/api/v1/workspaces/join \\
  -H "Authorization: Bearer $JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"join_code": "VR-9482-KLAX"}'`,
      response: `{
  "workspace_id": "ws_enterprise_01",
  "workspace_name": "Acme Global AI",
  "role": "MEMBER",
  "membership_status": "ACTIVE"
}`,
    },
  ]

  const current = endpoints.find((e) => e.id === activeEndpoint) || endpoints[0]

  const handleCopy = () => {
    navigator.clipboard.writeText(current.curl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const heroVisual = (
    <div className="w-full max-w-lg rounded-2xl border border-border/70 bg-[#0F172A] text-slate-100 p-6 shadow-2xl relative overflow-hidden font-mono text-xs">
      <div className="flex items-center justify-between pb-3 border-b border-slate-700/60 mb-3">
        <div className="flex items-center space-x-2">
          <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">POST</span>
          <span className="text-slate-300 text-xs">/api/v1/chat/sessions/stream</span>
        </div>
        <span className="text-[10px] text-slate-400 flex items-center gap-1">
          <Radio className="w-3 h-3 text-emerald-400 animate-pulse" />
          <span>text/event-stream</span>
        </span>
      </div>
      <p className="text-slate-400 text-[11px] mb-3">Real-time token and citation streaming protocol:</p>
      <div className="bg-slate-950/80 p-3 rounded-lg border border-slate-800 text-slate-300 leading-relaxed overflow-x-auto text-[11px]">
        <p className="text-emerald-400">event: token</p>
        <p className="text-slate-200">data: &#123;&quot;content&quot;: &quot;According to Section 14...&quot;&#125;</p>
        <p className="text-cyan-400 mt-2">event: citation</p>
        <p className="text-slate-200">data: &#123;&quot;id&quot;: 1, &quot;passage&quot;: &quot;Liability cap...&quot;&#125;</p>
        <p className="text-amber-400 mt-2">event: done</p>
        <p className="text-slate-200">data: &#123;&quot;reliability_score&quot;: 0.984&#125;</p>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col w-full">
      <MarketingHero
        badge="REST API & Streaming Protocol"
        title={
          <>
            Programmatic Control with{' '}
            <span className="text-primary">Enterprise REST & SSE APIs.</span>
          </>
        }
        subtitle="Integrate verifiable RAG into your internal portals, microservices, and client applications with predictable JSON endpoints and real-time SSE event streams."
        secondaryCtaText="Read Guides"
        secondaryCtaLink="/resources/documentation"
        visual={heroVisual}
      />

      {/* Interactive Explorer */}
      <section className="py-20 lg:py-28 border-t border-border/40">
        <div className="container mx-auto px-4 md:px-8 max-w-7xl">
          <FadeUp className="max-w-3xl mb-12" yOffset={20}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-primary/20 bg-primary/5 text-xs font-semibold text-primary mb-4">
              <Code2 className="w-3.5 h-3.5" />
              <span>Interactive Endpoint Reference</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-foreground">
              Core Endpoints at a Glance
            </h2>
            <p className="text-muted-foreground text-base md:text-lg mt-3">
              Explore request patterns, authentication requirements, and real streaming event schemas.
            </p>
          </FadeUp>

          <div className="grid lg:grid-cols-12 gap-8 items-start">
            {/* Endpoint Selector Tabs */}
            <div className="lg:col-span-4 space-y-2">
              {endpoints.map((ep) => {
                const isSelected = ep.id === activeEndpoint
                return (
                  <button
                    key={ep.id}
                    onClick={() => setActiveEndpoint(ep.id)}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${
                      isSelected
                        ? 'border-primary bg-surface-elevated shadow-sm'
                        : 'border-border/60 bg-surface/50 hover:bg-surface-elevated/40'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded font-bold bg-primary/10 text-primary">
                        {ep.method}
                      </span>
                      <span className="text-xs text-muted-foreground">{ep.tag}</span>
                    </div>
                    <p className="text-xs font-mono font-medium text-foreground truncate">{ep.path}</p>
                  </button>
                )
              })}
            </div>

            {/* Code & Payload Viewer */}
            <div className="lg:col-span-8 rounded-2xl border border-border/70 bg-[#0F172A] text-slate-100 p-6 md:p-8 shadow-xl font-mono text-xs">
              <div className="flex items-center justify-between pb-4 border-b border-slate-700/60 mb-6">
                <div>
                  <span className="px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-400 font-bold text-xs mr-2">
                    {current.method}
                  </span>
                  <span className="text-slate-200 text-sm font-semibold">{current.path}</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="flex items-center space-x-1.5 text-slate-400 hover:text-slate-200 transition-colors"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  <span>{copied ? 'Copied' : 'Copy cURL'}</span>
                </button>
              </div>

              <p className="font-sans text-slate-400 text-sm mb-6 leading-relaxed">{current.desc}</p>

              <div className="space-y-6">
                <div>
                  <p className="text-slate-400 uppercase tracking-wider text-[11px] mb-2 font-bold">Request (cURL)</p>
                  <pre className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-emerald-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                    {current.curl}
                  </pre>
                </div>

                <div>
                  <p className="text-slate-400 uppercase tracking-wider text-[11px] mb-2 font-bold">Response Payload</p>
                  <pre className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                    {current.response}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <MarketingCTA
        title="Ready to Integrate the Veritas API?"
        description="Deploy your workspace and start building with production-ready REST and SSE endpoints today."
      />
    </div>
  )
}
