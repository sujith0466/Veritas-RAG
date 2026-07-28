import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { cn } from '@/utils/cn'

interface MouseParallaxProps {
  children: React.ReactNode
  className?: string
  factor?: number // higher is more movement
}

export function MouseParallax({ children, className, factor = 15 }: MouseParallaxProps) {
  const shouldReduceMotion = useReducedMotion()
  const [position, setPosition] = useState({ x: 0, y: 0 })

  useEffect(() => {
    if (shouldReduceMotion) return

    const handleMouseMove = (e: MouseEvent) => {
      const x = (e.clientX / window.innerWidth - 0.5) * factor
      const y = (e.clientY / window.innerHeight - 0.5) * factor
      setPosition({ x, y })
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [factor, shouldReduceMotion])

  return (
    <motion.div
      animate={shouldReduceMotion ? { x: 0, y: 0 } : { x: position.x, y: position.y }}
      transition={{ type: "spring", stiffness: 150, damping: 15, mass: 0.5 }}
      className={cn("will-change-transform", className)}
    >
      {children}
    </motion.div>
  )
}
