import { AnimatedCounter } from '@/components/landing/AnimatedCounter'
import { Stagger } from '@/components/motion/Stagger'
import { FadeUp } from '@/components/motion/FadeUp'

const METRICS = [
  {
    value: 99.9,
    suffix: '%',
    label: 'Hallucination Reduction',
    description: 'Measured against baseline LLM outputs using our proprietary Reflection Engine.'
  },
  {
    value: 10,
    suffix: 'x',
    label: 'Faster Retrieval',
    description: 'Our hybrid sparse-dense indices return context in milliseconds.'
  },
  {
    value: 100,
    suffix: 'M+',
    label: 'Documents Indexed',
    description: 'Scales effortlessly from small startups to Fortune 500 enterprises.'
  },
  {
    value: 0,
    label: 'Data Leaks',
    description: 'SOC2 Type II compliant with strict RBAC boundary enforcement.'
  }
]

export function PlatformMetrics() {
  return (
    <section className="py-24 border-b border-border/40 bg-surface/30">
      <div className="container mx-auto px-4 md:px-8 max-w-7xl">
        <Stagger className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 lg:gap-8 divide-y md:divide-y-0 md:divide-x divide-border/40" staggerDelay={0.1}>
          {METRICS.map((metric) => (
            <FadeUp
              key={metric.label}
              yOffset={20}
              className="flex flex-col items-center text-center pt-8 md:pt-0 px-4 group"
            >
              <div className="text-4xl md:text-5xl font-bold text-foreground mb-4">
                <AnimatedCounter
                  value={metric.value}
                  suffix={metric.suffix}
                  decimals={metric.value % 1 !== 0 ? 1 : 0}
                  className="text-primary group-hover:text-primary/80 transition-colors"
                />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{metric.label}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {metric.description}
              </p>
            </FadeUp>
          ))}
        </Stagger>
      </div>
    </section>
  )
}
