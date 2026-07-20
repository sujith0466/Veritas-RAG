import { motion, AnimatePresence } from 'framer-motion'
import { loadingOverlayVariants } from '@/motion'
import { Spinner } from './Spinner'

interface GlobalLoadingOverlayProps {
  message?: string
}

export function GlobalLoadingOverlay({ message = 'Loading...' }: GlobalLoadingOverlayProps) {
  return (
    <AnimatePresence>
      <motion.div
        variants={loadingOverlayVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background/80 backdrop-blur-md"
        aria-live="assertive"
      >
        <Spinner size="lg" className="mb-4 text-primary" />
        <motion.p
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="text-sm font-medium text-muted-foreground"
        >
          {message}
        </motion.p>
      </motion.div>
    </AnimatePresence>
  )
}
