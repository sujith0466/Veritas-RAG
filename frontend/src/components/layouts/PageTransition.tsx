import { motion } from 'framer-motion'
import { pageTransitionVariants } from '@/motion'
import { cn } from '@/utils/cn'

interface PageTransitionProps {
  children: React.ReactNode
  className?: string
}

export function PageTransition({ children, className }: PageTransitionProps) {
  return (
    <motion.div
      variants={pageTransitionVariants}
      initial="initial"
      animate="enter"
      exit="exit"
      className={cn('w-full h-full', className)}
    >
      {children}
    </motion.div>
  )
}
