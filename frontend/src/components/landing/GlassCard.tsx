import { motion, HTMLMotionProps } from 'framer-motion'
import { cn } from '@/utils/cn'
import { forwardRef } from 'react'

export interface GlassCardProps extends HTMLMotionProps<'div'> {
  className?: string
  children: React.ReactNode
  interactive?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg' | 'xl'
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className, children, interactive = false, padding = 'lg', ...props }, ref) => {
    const paddingStyles = {
      none: '',
      sm: 'p-4',
      md: 'p-6',
      lg: 'p-8',
      xl: 'p-10 md:p-12',
    }

    return (
      <motion.div
        ref={ref}
        className={cn(
          "relative overflow-hidden rounded-2xl border border-border bg-surface shadow-sm",
          interactive && "transition-all duration-300 hover:border-primary/50 hover:shadow-md hover:bg-surface-elevated cursor-pointer group",
          paddingStyles[padding],
          className
        )}
        whileHover={interactive ? { y: -4 } : undefined}
        {...props}
      >
        {/* Subtle glass reflection overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/[0.05] to-transparent opacity-0 transition-opacity duration-500 pointer-events-none group-hover:opacity-100" />

        <div className="relative z-10">
          {children}
        </div>
      </motion.div>
    )
  }
)

GlassCard.displayName = 'GlassCard'
