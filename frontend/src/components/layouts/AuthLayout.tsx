import { Outlet } from 'react-router-dom'
import { motion } from 'framer-motion'
import { BackgroundProvider } from '../backgrounds'
import { Shield } from 'lucide-react'

export function AuthLayout() {
  return (
    <div className="relative min-h-screen w-full flex items-center justify-center p-4">
      <BackgroundProvider type="aurora" />
      
      <div className="w-full max-w-md relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary mb-4 backdrop-blur-sm border border-primary/20">
            <Shield className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">RAGuard AI</h1>
          <p className="text-sm text-muted-foreground mt-1 text-center">
            Enterprise Retrieval-Augmented Generation Security
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="rounded-2xl border border-border bg-surface-elevated/80 p-8 shadow-modal backdrop-blur-xl"
        >
          <Outlet />
        </motion.div>
      </div>
    </div>
  )
}
