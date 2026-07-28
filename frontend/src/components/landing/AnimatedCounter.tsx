import { useEffect, useRef, useState } from 'react'
import { useInView, useSpring } from 'framer-motion'
import { cn } from '@/utils/cn'

interface AnimatedCounterProps {
  value: number
  suffix?: string
  prefix?: string
  duration?: number
  className?: string
  decimals?: number
}

export function AnimatedCounter({ 
  value, 
  suffix = '', 
  prefix = '', 
  duration = 2, 
  className,
  decimals = 0
}: AnimatedCounterProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true, margin: "-50px" })
  const [displayValue, setDisplayValue] = useState("0")
  
  const spring = useSpring(0, {
    duration: duration * 1000,
    bounce: 0,
  })

  useEffect(() => {
    if (isInView) {
      spring.set(value)
    }
  }, [isInView, spring, value])

  useEffect(() => {
    return spring.on('change', (latest) => {
      if (ref.current) {
        setDisplayValue(latest.toFixed(decimals))
      }
    })
  }, [spring, decimals])

  return (
    <span 
      ref={ref} 
      className={cn("tabular-nums tracking-tight font-bold", className)}
      aria-label={`${prefix}${value}${suffix}`}
    >
      {prefix}{displayValue}{suffix}
    </span>
  )
}
