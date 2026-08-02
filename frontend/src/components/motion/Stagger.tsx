import { motion, useReducedMotion, Variants } from 'framer-motion'
import { cn } from '@/utils/cn'
import { Children, isValidElement } from 'react'

interface StaggerProps {
  children: React.ReactNode
  className?: string
  staggerDelay?: number
  initialDelay?: number
}

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
}

const reducedItemVariants: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 }
}

export function Stagger({
  children,
  className,
  staggerDelay = 0.1,
  initialDelay = 0
}: StaggerProps) {
  const shouldReduceMotion = useReducedMotion()

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: shouldReduceMotion ? 0 : staggerDelay,
        delayChildren: initialDelay,
      }
    }
  }

  // Ensure children are wrapped in motion components if they aren't already
  // Usually this is done manually, but we can just provide the container
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-50px" }}
      className={cn(className)}
    >
      {Children.map(children, child => {
        if (!isValidElement(child)) return child
        return (
          <motion.div variants={shouldReduceMotion ? reducedItemVariants : itemVariants}>
            {child}
          </motion.div>
        )
      })}
    </motion.div>
  )
}
