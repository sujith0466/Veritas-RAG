import { cn } from '@/utils/cn'
import { motion } from 'framer-motion'
import { cardVariants } from '@/motion'
import { AlertTriangle, RefreshCcw } from 'lucide-react'
import { Button } from './Button'

interface ErrorStateProps {
  title?: string
  error: Error | null
  onRetry?: () => void
  className?: string
}

export function ErrorState({
  title = 'Something went wrong',
  error,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <motion.div
      variants={cardVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-danger/20 bg-danger/5 p-8 text-center',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-danger/10 mb-4">
        <AlertTriangle className="h-6 w-6 text-danger" />
      </div>
      <h3 className="text-lg font-semibold text-danger-foreground">{title}</h3>
      <p className="mt-2 text-sm text-danger/80 max-w-md">
        {error?.message || 'An unexpected error occurred while loading this content.'}
      </p>
      {onRetry && (
        <Button onClick={onRetry} variant="outline" className="mt-6">
          <RefreshCcw className="mr-2 h-4 w-4" />
          Try Again
        </Button>
      )}
    </motion.div>
  )
}
