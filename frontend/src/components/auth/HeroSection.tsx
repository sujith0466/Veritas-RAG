import { motion, AnimatePresence } from 'framer-motion'
import { useState, useEffect } from 'react'
import { Shield, Server, Lock, Zap, Search, Activity, Cpu } from 'lucide-react'

const FEATURES = [
  { icon: <Activity className="w-5 h-5" />, title: 'AI Reliability Scoring' },
  { icon: <Search className="w-5 h-5" />, title: 'Hybrid Retrieval' },
  { icon: <Server className="w-5 h-5" />, title: 'Vector Intelligence' },
  { icon: <Cpu className="w-5 h-5" />, title: 'Knowledge Management' },
  { icon: <Zap className="w-5 h-5" />, title: 'Explainable AI' },
  { icon: <Lock className="w-5 h-5" />, title: 'Enterprise Security' },
]

const TRUST_BADGES = [
  'Enterprise Ready',
  'Secure Authentication',
  'Multi-Tenant',
  'RBAC Protected',
  'Production Ready'
]

export function HeroSection() {
  const [currentFeature, setCurrentFeature] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentFeature((prev) => (prev + 1) % FEATURES.length)
    }, 6000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex flex-col justify-center h-full max-w-lg mx-auto lg:mx-0 p-8 lg:p-12 relative z-10 text-foreground">

      {/* Logo & Subtitle */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="mb-8"
      >
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/20 text-primary mb-6 backdrop-blur-md border border-primary/30 shadow-[0_0_40px_rgba(59,130,246,0.3)]">
          <Shield className="h-8 w-8" />
        </div>
        <h1 className="text-4xl lg:text-5xl font-bold tracking-tight mb-4">
          Veritas RAG
        </h1>
        <h2 className="text-xl text-primary font-medium tracking-wide">
          Enterprise Knowledge Reliability Platform
        </h2>
      </motion.div>

      {/* Description */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2 }}
        className="mb-12 border-l-2 border-primary/40 pl-6"
      >
        <p className="text-muted-foreground text-lg leading-relaxed">
          Build, evaluate, monitor, and improve Retrieval-Augmented Generation systems using explainable AI, hybrid retrieval, enterprise security, and production-grade reliability.
        </p>
      </motion.div>

      {/* Rotating Feature Cards */}
      <div className="h-24 mb-12">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentFeature}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-4 bg-surface-elevated/30 backdrop-blur-md border border-border/50 p-4 rounded-xl shadow-lg w-fit"
          >
            <div className="p-3 bg-primary/20 rounded-lg text-primary">
              {FEATURES[currentFeature].icon}
            </div>
            <span className="font-semibold text-foreground text-lg">
              {FEATURES[currentFeature].title}
            </span>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Trust Badges */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.6 }}
      >
        <p className="text-xs uppercase tracking-widest text-muted-foreground mb-4 font-semibold">
          Trusted Standards
        </p>
        <div className="flex flex-wrap gap-3">
          {TRUST_BADGES.map((badge) => (
            <motion.div
              key={badge}
              whileHover={{ scale: 1.05, backgroundColor: 'rgba(59, 130, 246, 0.1)' }}
              className="px-3 py-1.5 rounded-full bg-surface-elevated/20 border border-border/50 text-xs text-muted-foreground backdrop-blur-sm cursor-default transition-colors"
            >
              {badge}
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}
