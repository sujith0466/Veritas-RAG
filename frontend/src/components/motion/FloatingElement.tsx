import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/utils/cn'

interface FloatingElementProps {
  children: React.ReactNode
  className?: string
  yOffset?: number
  duration?: number
  delay?: number
}

export function FloatingElement({
  children,
  className,
  yOffset = 10,
  duration = 4,
  delay = 0
}: FloatingElementProps) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      animate={shouldReduceMotion ? {} : { y: [0, -yOffset, 0] }}
      transition={{
        repeat: Infinity,
        duration,
        delay,
        ease: "easeInOut"
      }}
      className={cn("will-change-transform", className)}
    >
      {children}
    </motion.div>
  )
}
