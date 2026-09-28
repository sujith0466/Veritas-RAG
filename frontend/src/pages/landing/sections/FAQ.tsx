import { useState } from 'react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import {
  ChevronDown,
  HelpCircle,
  ShieldCheck,
  Cpu,
  Layers,
  Sparkles,
  Search,
  BookOpen,
  CheckCircle2,
} from 'lucide-react'
import { FadeUp } from '@/components/motion/FadeUp'
import { cn } from '@/utils/cn'

interface FAQItem {
  id: string
  number: string
  question: string
  answer: string
  category: string
  evidenceBadge: string
  icon: typeof HelpCircle
}

const FAQS: FAQItem[] = [
  {
    id: 'faq-1',
    number: '01',
    question: 'What is Veritas RAG?',
    answer:
      'Veritas RAG is an enterprise-grade platform that secures, monitors, and optimizes Retrieval-Augmented Generation (RAG) pipelines. It provides the infrastructure needed to build hallucination-resistant, fully explainable AI applications grounded in your private knowledge.',
    category: 'PLATFORM OVERVIEW',
    evidenceBadge: 'Core Architecture · Grounded Retrieval',
    icon: Layers,
  },
  {
    id: 'faq-2',
    number: '02',
    question: 'How is it different from traditional RAG?',
    answer:
      'While traditional RAG simply retrieves documents and passes them to an LLM, Veritas RAG introduces a Reflection Engine, Hybrid Search, and strict Role-Based Access Control. It actively evaluates retrieval quality, detects hallucinations before generation, and enforces that users only access data they are authorized to retrieve.',
    category: 'PIPELINE DIFFERENTIATION',
    evidenceBadge: 'Reflection Engine · Hybrid Search · Strict RBAC',
    icon: Search,
  },
  {
    id: 'faq-3',
    number: '03',
    question: 'Which LLMs are supported?',
    answer:
      'Veritas RAG is model-agnostic. Our headless architecture integrates seamlessly with OpenAI, Anthropic, Google Gemini, Azure OpenAI, and open-source models hosted on platforms like vLLM or Ollama.',
    category: 'MODEL COMPATIBILITY',
    evidenceBadge: 'Headless API · Multi-Provider Routing',
    icon: Cpu,
  },
  {
    id: 'faq-4',
    number: '04',
    question: 'Can it be deployed on-premises?',
    answer:
      'Yes. Veritas RAG is built using containerized microservices and can be deployed fully on-premises, in your private VPC, or consumed as a managed cloud service depending on your compliance requirements.',
    category: 'DEPLOYMENT ARCHITECTURE',
    evidenceBadge: 'Private VPC · Air-Gapped / On-Premises',
    icon: ShieldCheck,
  },
  {
    id: 'faq-5',
    number: '05',
    question: 'How does reliability scoring work?',
    answer:
      'Our Reflection Engine evaluates the retrieved context against the user query, and subsequently scores the LLM output against the retrieved context. It measures factual consistency, source attribution, and contextual relevance to generate a continuous reliability score.',
    category: 'RELIABILITY VALIDATION',
    evidenceBadge: 'Factual Consistency · Attribution Scoring',
    icon: Sparkles,
  },
  {
    id: 'faq-6',
    number: '06',
    question: 'Is it suitable for enterprise environments?',
    answer:
      'Absolutely. We designed Veritas RAG specifically for enterprise scale and governance. It features SOC2-aligned architecture, comprehensive audit logs, tenant isolation, and granular RBAC to meet the demands of enterprise security teams.',
    category: 'ENTERPRISE GOVERNANCE',
    evidenceBadge: 'Audit Telemetry · Multi-Tenant Isolation',
    icon: BookOpen,
  },
]

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0)
  const shouldReduceMotion = useReducedMotion()

  return (
    <section
      id="faq"
      aria-label="Frequently Asked Questions"
      className="py-28 md:py-36 bg-surface/30 border-t border-border/70 relative overflow-hidden"
    >
      {/* ─── Ambient Atmospheric Background ─── */}
      <div className="absolute inset-0 pointer-events-none -z-10 overflow-hidden">
        <div className="absolute top-1/4 right-1/4 w-[600px] h-[500px] bg-teal-500/[0.025] rounded-full blur-[130px]" />
        <div className="absolute bottom-1/3 left-1/4 w-[500px] h-[400px] bg-sky-500/[0.02] rounded-full blur-[120px]" />

        {/* Subtle coordinate mesh */}
        <div
          className="absolute inset-0 opacity-[0.025] dark:opacity-[0.04]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, hsl(var(--foreground)) 1px, transparent 0)`,
            backgroundSize: '32px 32px',
          }}
        />
      </div>

      <div className="container mx-auto px-4 md:px-8 max-w-6xl relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
          {/* ─── Left Column: Title, Subtitle & Evidence Status Card ─── */}
          <div className="lg:col-span-5 flex flex-col justify-between h-full">
            <FadeUp>
              <div className="text-left">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface border border-border/80 shadow-xs mb-4 text-xs font-mono font-medium text-muted-foreground">
                  <span className="w-1.5 h-1.5 rounded-full bg-teal-600 animate-pulse" />
                  <span>KNOWLEDGE BASE & ARCHITECTURE FAQ</span>
                </div>

                <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-foreground leading-[1.15] mb-4">
                  Frequently Asked Questions.
                </h2>

                <p className="text-base md:text-lg text-muted-foreground leading-relaxed mb-8">
                  Everything you need to know about the platform and how it integrates into your infrastructure.
                </p>

                {/* ─── Knowledge Signal Summary Card ─── */}
                <div className="rounded-2xl p-6 bg-surface/80 backdrop-blur-md border border-border/80 shadow-card space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-teal-500/10 border border-teal-600/30 flex items-center justify-center text-teal-700 dark:text-teal-400 flex-shrink-0">
                      <ShieldCheck className="w-5 h-5" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-foreground">
                        Enterprise Knowledge Assurance
                      </h4>
                      <p className="text-2xs font-mono text-muted-foreground">
                        Structured, verifiable RAG specifications
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2 pt-2 border-t border-border/50 text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 flex-shrink-0" />
                      <span>Model-Agnostic Headless Integration</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 flex-shrink-0" />
                      <span>Private VPC & Containerized On-Premises</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 flex-shrink-0" />
                      <span>Strict Multi-Tenant Isolation by Default</span>
                    </div>
                  </div>
                </div>
              </div>
            </FadeUp>
          </div>

          {/* ─── Right Column: Interactive Knowledge Accordion ─── */}
          <div className="lg:col-span-7 space-y-3.5">
            {FAQS.map((faq, i) => {
              const isOpen = openIndex === i
              const IconComponent = faq.icon

              return (
                <FadeUp key={faq.id} delay={i * 0.05}>
                  <div
                    className={cn(
                      'rounded-2xl transition-all duration-300 relative select-none overflow-hidden border',
                      'bg-surface/85 backdrop-blur-md',
                      isOpen
                        ? 'border-teal-600/40 shadow-[0_12px_32px_rgba(15,118,110,0.08)] bg-surface'
                        : 'border-border/70 shadow-xs hover:border-border hover:shadow-card'
                    )}
                    style={{
                      transform: isOpen && !shouldReduceMotion ? 'translateZ(4px)' : 'none',
                    }}
                  >
                    {/* Left laser accent line when open */}
                    {isOpen && (
                      <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-teal-600 to-sky-500 rounded-r-full" />
                    )}

                    {/* Question Button Header */}
                    <button
                      type="button"
                      id={`faq-btn-${i}`}
                      aria-expanded={isOpen}
                      aria-controls={`faq-answer-${i}`}
                      onClick={() => setOpenIndex(isOpen ? null : i)}
                      className="w-full flex items-start justify-between p-5 md:p-6 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 transition-colors gap-4"
                    >
                      <div className="flex items-start gap-3.5 min-w-0">
                        <span
                          className={cn(
                            'text-xs font-mono font-bold pt-0.5 flex-shrink-0 transition-colors',
                            isOpen ? 'text-teal-700 dark:text-teal-400' : 'text-muted-foreground/70'
                          )}
                        >
                          {faq.number}
                        </span>

                        <div>
                          <div className="flex items-center gap-1.5 mb-1">
                            <IconComponent className="w-3.5 h-3.5 text-teal-600 flex-shrink-0" />
                            <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-muted-foreground/80">
                              {faq.category}
                            </span>
                          </div>
                          <span
                            className={cn(
                              'text-base md:text-lg font-semibold tracking-tight transition-colors leading-snug block',
                              isOpen ? 'text-foreground' : 'text-foreground/90 hover:text-foreground'
                            )}
                          >
                            {faq.question}
                          </span>
                        </div>
                      </div>

                      <div
                        className={cn(
                          'w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-300 border ml-2',
                          isOpen
                            ? 'bg-teal-500/10 border-teal-600/30 text-teal-700 dark:text-teal-400'
                            : 'bg-muted/50 border-border/50 text-muted-foreground'
                        )}
                      >
                        <motion.div
                          animate={{ rotate: isOpen ? 180 : 0 }}
                          transition={{ duration: 0.25, ease: 'easeOut' }}
                        >
                          <ChevronDown className="w-4 h-4" />
                        </motion.div>
                      </div>
                    </button>

                    {/* Expandable Answer Panel */}
                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          id={`faq-answer-${i}`}
                          role="region"
                          aria-labelledby={`faq-btn-${i}`}
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: 'easeInOut' }}
                        >
                          <div className="px-5 md:px-6 pb-6 pt-1">
                            <div className="border-t border-border/50 pt-4">
                              <p className="text-sm md:text-[15px] text-muted-foreground leading-relaxed mb-4">
                                {faq.answer}
                              </p>

                              {/* Evidence/Platform Knowledge Tag Footer */}
                              <div className="flex items-center justify-between pt-3 border-t border-border/40 text-2xs font-mono text-muted-foreground">
                                <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-400 font-semibold">
                                  <span className="w-1.5 h-1.5 rounded-full bg-teal-600" />
                                  <span>VERIFIED SPECIFICATION</span>
                                </div>

                                <span className="text-muted-foreground truncate pl-2">
                                  {faq.evidenceBadge}
                                </span>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </FadeUp>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
