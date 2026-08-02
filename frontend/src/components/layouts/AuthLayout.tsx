import { Outlet } from 'react-router-dom'
import { FloatingBackground } from '../auth/FloatingBackground'
import { motion } from 'framer-motion'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'
import { Shield } from 'lucide-react'

export function AuthLayout() {
  return (
    <MarketingThemeProvider>
      <div className="relative min-h-screen w-full flex flex-col items-center justify-center p-4 overflow-x-hidden">
        <FloatingBackground />

        {/* Top Branding / Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="relative z-10 text-center mb-8 flex flex-col items-center"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-6 border border-primary/20 shadow-sm">
            <Shield className="h-8 w-8" />
          </div>
          <h1 className="text-3xl lg:text-4xl font-bold tracking-tight text-foreground mb-2">
            Welcome to RAGuard AI
          </h1>
          <p className="text-muted-foreground text-lg">
            Access your secure RAG reliability workspace.
          </p>
        </motion.div>

        {/* Main Authentication Card */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="w-full max-w-lg relative z-10"
        >
          <div className="rounded-[24px] bg-surface/90 backdrop-blur-xl border border-border/50 p-8 sm:p-10 shadow-2xl relative overflow-hidden transition-all hover:shadow-primary/5">
            <Outlet />
          </div>
        </motion.div>

        {/* Trust Indicators / Footer */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="relative z-10 mt-12 flex flex-col items-center gap-6"
        >
          <div className="flex flex-wrap justify-center gap-3 max-w-2xl px-4">
            {['Enterprise Ready', 'Secure Authentication', 'Multi-Tenant', 'Explainable AI', 'Production Ready'].map((badge) => (
              <span key={badge} className="px-3 py-1.5 rounded-full bg-surface-elevated/50 border border-border/50 text-xs font-medium text-muted-foreground backdrop-blur-sm">
                {badge}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted-foreground/60">
            © {new Date().getFullYear()} RAGuard AI. All rights reserved.
          </p>
        </motion.div>
      </div>
    </MarketingThemeProvider>
  )
}
