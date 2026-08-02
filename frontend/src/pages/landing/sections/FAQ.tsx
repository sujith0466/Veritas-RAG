import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown } from 'lucide-react'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'

const FAQS = [
  {
    question: 'What is RAGuard AI?',
    answer: 'RAGuard AI is an enterprise-grade platform that secures, monitors, and optimizes Retrieval-Augmented Generation (RAG) pipelines. It provides the infrastructure needed to build hallucination-resistant, fully explainable AI applications grounded in your private knowledge.'
  },
  {
    question: 'How is it different from traditional RAG?',
    answer: 'While traditional RAG simply retrieves documents and passes them to an LLM, RAGuard AI introduces a Reflection Engine, Hybrid Search, and strict Role-Based Access Control. It actively evaluates retrieval quality, detects hallucinations before generation, and guarantees that users only see data they are authorized to access.'
  },
  {
    question: 'Which LLMs are supported?',
    answer: 'RAGuard AI is model-agnostic. Our headless architecture integrates seamlessly with OpenAI, Anthropic, Google Gemini, Azure OpenAI, and open-source models hosted on platforms like vLLM or Ollama.'
  },
  {
    question: 'Can it be deployed on-premises?',
    answer: 'Yes. RAGuard AI is built using containerized microservices and can be deployed fully on-premises, in your private VPC, or consumed as a managed cloud service depending on your compliance requirements.'
  },
  {
    question: 'How does reliability scoring work?',
    answer: 'Our proprietary Reflection Engine evaluates the retrieved context against the user query, and subsequently scores the LLM output against the retrieved context. It measures factual consistency, source attribution, and contextual relevance to generate a continuous reliability score.'
  },
  {
    question: 'Is it suitable for enterprise environments?',
    answer: 'Absolutely. We designed RAGuard AI specifically for enterprise scale and governance. It features SOC2-compliant architecture, comprehensive audit logs, strict tenant isolation, and granular RBAC to meet the demands of Fortune 500 security teams.'
  }
]

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0)

  return (
    <section className="py-24 bg-surface/30 border-t border-border/40">
      <div className="container mx-auto px-4 md:px-8 max-w-4xl">
        <FadeUp>
          <SectionHeading
            title="Frequently Asked Questions."
            subtitle="Everything you need to know about the platform and how it integrates into your infrastructure."
            className="mb-16"
          />
        </FadeUp>

        <Stagger className="space-y-4" staggerDelay={0.1}>
          {FAQS.map((faq, i) => {
            const isOpen = openIndex === i

            return (
              <FadeUp key={faq.question} yOffset={10}>
                <div
                  className="border border-border/40 rounded-xl bg-surface/50 backdrop-blur-sm overflow-hidden transition-colors hover:border-border/80"
                >
                  <button
                    onClick={() => setOpenIndex(isOpen ? null : i)}
                    className="w-full flex items-center justify-between p-6 text-left focus:outline-none focus-visible:bg-surface-elevated transition-colors"
                  >
                    <span className="font-medium text-foreground">{faq.question}</span>
                    <motion.span
                      animate={{ rotate: isOpen ? 180 : 0 }}
                      transition={{ duration: 0.3, ease: 'easeOut' }}
                      className="text-muted-foreground shrink-0 ml-4 flex items-center justify-center"
                    >
                      <ChevronDown className="w-5 h-5" />
                    </motion.span>
                  </button>

                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: "easeInOut" }}
                      >
                        <div className="px-6 pb-6 text-sm text-muted-foreground leading-relaxed border-t border-border/40 pt-4">
                          {faq.answer}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </FadeUp>
            )
          })}
        </Stagger>
      </div>
    </section>
  )
}
