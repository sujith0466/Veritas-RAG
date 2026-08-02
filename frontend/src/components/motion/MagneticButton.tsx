import { motion, useReducedMotion, HTMLMotionProps } from 'framer-motion'
import { useState, useRef } from 'react'
import { cn } from '@/utils/cn'

interface MagneticButtonProps extends HTMLMotionProps<"button"> {
  children: React.ReactNode
  strength?: number
  className?: string
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost'
}

export function MagneticButton({
  children,
  strength = 15,
  className,
  variant = 'primary',
  ...props
}: MagneticButtonProps) {
  const ref = useRef<HTMLButtonElement>(null)
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const shouldReduceMotion = useReducedMotion()

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (shouldReduceMotion || !ref.current) return
    const { clientX, clientY } = e
    const { height, width, left, top } = ref.current.getBoundingClientRect()
    const middleX = clientX - (left + width / 2)
    const middleY = clientY - (top + height / 2)
    setPosition({ x: middleX * (strength / width), y: middleY * (strength / height) })
  }

  const reset = () => setPosition({ x: 0, y: 0 })

  const baseClasses = "relative inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 disabled:pointer-events-none px-4 py-2 h-10 w-full sm:w-auto overflow-hidden group"

  const variants = {
    primary: "bg-primary text-primary-foreground shadow-md hover:bg-primary/90",
    secondary: "bg-surface-elevated text-foreground hover:bg-muted shadow-sm",
    outline: "border border-border/60 bg-transparent hover:bg-muted text-foreground",
    ghost: "hover:bg-muted hover:text-foreground text-muted-foreground",
  }

  return (
    <motion.button
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={reset}
      animate={shouldReduceMotion ? { x: 0, y: 0 } : { x: position.x, y: position.y }}
      transition={{ type: "spring", stiffness: 150, damping: 15, mass: 0.1 }}
      className={cn(baseClasses, variants[variant], className)}
      {...props}
    >
      <div className="relative z-10 flex items-center justify-center gap-2 pointer-events-none">
        {children}
      </div>

      {/* Ripple/Glow effect on hover */}
      {!shouldReduceMotion && (
        <div className="absolute inset-0 bg-white/0 group-hover:bg-white/10 transition-colors duration-300 pointer-events-none" />
      )}
    </motion.button>
  )
}
