import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/utils/cn'

interface FadeUpProps {
  children: React.ReactNode
  className?: string
  delay?: number
  duration?: number
  yOffset?: number
}

export function FadeUp({
  children,
  className,
  delay = 0,
  duration = 0.5,
  yOffset = 20
}: FadeUpProps) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      initial={{ opacity: 0, y: shouldReduceMotion ? 0 : yOffset }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration, delay, ease: "easeOut" }}
      className={cn(className)}
    >
      {children}
    </motion.div>
  )
}
