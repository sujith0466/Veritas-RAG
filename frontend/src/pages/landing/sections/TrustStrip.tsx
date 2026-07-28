import { ShieldCheck, Users, Brain, FileSearch, Link2, Building2 } from 'lucide-react'
import { Stagger } from '@/components/motion/Stagger'
import { FadeUp } from '@/components/motion/FadeUp'
import { motion } from 'framer-motion'

const BADGES = [
  { label: 'Multi-Tenant', icon: Users },
  { label: 'RBAC Protected', icon: ShieldCheck },
  { label: 'Explainable AI', icon: Brain },
  { label: 'Hybrid Retrieval', icon: FileSearch },
  { label: 'Source Attribution', icon: Link2 },
  { label: 'Enterprise Ready', icon: Building2 },
]

export function TrustStrip() {
  return (
    <div className="w-full flex flex-col items-center justify-center space-y-6">
      <FadeUp>
        <p className="text-sm font-medium text-muted-foreground uppercase tracking-widest">
          Trusted by Enterprise Engineering Teams
        </p>
      </FadeUp>
      
      <Stagger className="flex flex-wrap justify-center gap-4 md:gap-8" staggerDelay={0.1}>
        {BADGES.map((badge) => (
          <FadeUp key={badge.label} yOffset={10}>
            <motion.div
              whileHover={{ y: -3, scale: 1.05 }}
              className="flex items-center space-x-2 text-muted-foreground hover:text-foreground transition-colors px-4 py-2 rounded-lg bg-surface/30 backdrop-blur-sm border border-border/40 shadow-sm cursor-default"
            >
              <badge.icon className="w-4 h-4 opacity-70" />
              <span className="text-sm font-medium">{badge.label}</span>
            </motion.div>
          </FadeUp>
        ))}
      </Stagger>
    </div>
  )
}
