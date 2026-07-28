import { motion } from 'framer-motion'
import { cn } from '@/utils/cn'

interface AnimatedUnderlineProps {
  children: React.ReactNode
  className?: string
  color?: string
}

export function AnimatedUnderline({ 
  children, 
  className,
  color = 'var(--primary)'
}: AnimatedUnderlineProps) {
  return (
    <span className={cn("relative inline-block", className)}>
      {children}
      <motion.div
        initial={{ scaleX: 0 }}
        whileInView={{ scaleX: 1 }}
        viewport={{ once: true, margin: "-50px" }}
        transition={{ duration: 0.8, ease: "easeOut", delay: 0.5 }}
        style={{ originX: 0, backgroundColor: color }}
        className="absolute -bottom-1 left-0 w-full h-[4px] rounded-full opacity-50"
      />
    </span>
  )
}
