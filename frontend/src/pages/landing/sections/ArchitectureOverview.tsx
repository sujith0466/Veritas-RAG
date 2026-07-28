import { motion } from 'framer-motion'
import { SectionHeading } from '@/components/landing/SectionHeading'
import { FadeUp } from '@/components/motion/FadeUp'
import { Stagger } from '@/components/motion/Stagger'
import { cn } from '@/utils/cn'

const ARCHITECTURE_STEPS = [
  { id: 'sources', label: 'Knowledge Sources', description: 'APIs, Databases, Documents' },
  { id: 'processing', label: 'Document Processing', description: 'Intelligent Chunking & Metadata' },
  { id: 'embeddings', label: 'Embeddings', description: 'Dense & Sparse Vectors' },
  { id: 'vectordb', label: 'Vector Database', description: 'Qdrant / Enterprise Store' },
  { id: 'retrieval', label: 'Hybrid Retrieval', description: 'Keyword + Semantic Search' },
  { id: 'reflection', label: 'Reflection Engine', description: 'Query Rewriting & Re-ranking' },
  { id: 'llm', label: 'LLM Synthesis', description: 'Grounded Generation' },
  { id: 'validation', label: 'Reliability Validation', description: 'Hallucination Checks' },
  { id: 'response', label: 'Grounded Response', description: 'Secure, Attributed Output' },
]

export function ArchitectureOverview() {
  return (
    <section id="architecture" className="py-24 bg-surface border-t border-border relative overflow-hidden">
      <div className="container mx-auto px-4 md:px-8 max-w-4xl relative z-10">
        <FadeUp>
          <SectionHeading
            title="How RAGuard Works."
            subtitle="A transparent, end-to-end view of our reliability pipeline."
            className="mb-16"
          />
        </FadeUp>

        <div className="relative flex flex-col items-center">
          {/* Central connecting line */}
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-border pointer-events-none" />
          
          <motion.div 
            className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-gradient-to-b from-primary via-primary/50 to-primary origin-top pointer-events-none"
            initial={{ scaleY: 0 }}
            whileInView={{ scaleY: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 2, ease: "linear" }}
          />

          <Stagger className="flex flex-col space-y-8 w-full z-10 relative" staggerDelay={0.15}>
            {ARCHITECTURE_STEPS.map((step, i) => (
              <FadeUp
                key={step.id}
                yOffset={20}
                className={cn(
                  "relative flex items-center w-full",
                  i % 2 === 0 ? "justify-start" : "justify-end"
                )}
              >
                <div className={cn(
                  "w-[45%] md:w-[40%] bg-surface border border-border p-5 rounded-xl shadow-sm hover:border-primary/50 hover:shadow-md transition-all cursor-default",
                  i % 2 === 0 ? "text-right mr-auto" : "text-left ml-auto"
                )}>
                  <h4 className="font-bold text-foreground mb-1">{step.label}</h4>
                  <p className="text-xs text-muted-foreground">{step.description}</p>
                </div>

                {/* Node indicator */}
                <div className="absolute left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-background border-2 border-primary z-20 shadow-sm" />
              </FadeUp>
            ))}
          </Stagger>
        </div>
      </div>
    </section>
  )
}
