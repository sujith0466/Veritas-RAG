import { Outlet } from 'react-router-dom'
import { AuthArchitecturalPipeline } from '../auth/AuthArchitecturalPipeline'
import { motion } from 'framer-motion'
import { MarketingThemeProvider } from '@/providers/MarketingThemeProvider'

export function AuthLayout() {
  return (
    <MarketingThemeProvider>
      <div className="relative min-h-screen w-full flex flex-col items-center justify-center p-4 overflow-x-hidden">
        <AuthArchitecturalPipeline />



        {/* Main Authentication Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="w-full max-w-lg relative z-10"
        >
          <div className="rounded-[24px] bg-surface/95 backdrop-blur-md border border-border/60 p-6 sm:p-10 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.1)] ring-1 ring-black/[0.02] relative overflow-hidden transition-all duration-500 hover:shadow-[0_16px_60px_-15px_rgba(0,0,0,0.1)] hover:border-primary/20">
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
            © {new Date().getFullYear()} Veritas RAG. All rights reserved.
          </p>
        </motion.div>
      </div>
    </MarketingThemeProvider>
  )
}
