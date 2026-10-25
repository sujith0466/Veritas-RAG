import { motion, useReducedMotion } from 'framer-motion'
import { pageTransitionVariants, workspacePageVariants, pageFadeVariants } from '@/motion'
import { cn } from '@/utils/cn'

interface PageTransitionProps {
  children: React.ReactNode
  className?: string
  variant?: 'standard' | 'workspace' | 'fade'
}

export function PageTransition({ children, className, variant = 'standard' }: PageTransitionProps) {
  const shouldReduceMotion = useReducedMotion()

  const selectedVariants =
    variant === 'workspace'
      ? workspacePageVariants
      : variant === 'fade'
      ? pageFadeVariants
      : pageTransitionVariants

  return (
    <motion.div
      variants={shouldReduceMotion ? pageFadeVariants : selectedVariants}
      initial="initial"
      animate="enter"
      exit="exit"
      className={cn('w-full h-full', className)}
    >
      {children}
    </motion.div>
  )
}
