import { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'



/**
 * VectorFieldLayer — interactive dot-grid background with cursor-reactive highlight.
 * The primary grid is muted; a parallax-shifted highlight layer follows the cursor.
 */
export function VectorFieldLayer() {
  const shouldReduceMotion = useReducedMotion()
  const [mousePosition, setMousePosition] = useState({ x: 0.5, y: 0.3 })

  useEffect(() => {
    if (shouldReduceMotion) return
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
      })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [shouldReduceMotion])

  const parallaxX = (mousePosition.x - 0.5) * -20
  const parallaxY = (mousePosition.y - 0.5) * -20

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-[1] opacity-60">
      {/* Base dot grid */}
      <div
        className="absolute inset-[-5%]"
        style={{
          backgroundImage: 'radial-gradient(circle, hsl(215 20% 65% / 0.5) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
          maskImage: 'linear-gradient(to bottom, transparent 0%, black 15%, black 85%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 15%, black 85%, transparent 100%)',
        }}
      />

      {/* Cursor-reactive teal highlight grid overlay */}
      <motion.div
        className="absolute inset-[-10%]"
        animate={shouldReduceMotion ? { x: 0, y: 0 } : { x: parallaxX, y: parallaxY }}
        transition={{ type: 'spring', stiffness: 60, damping: 25 }}
        style={{
          backgroundImage: 'radial-gradient(circle, hsl(175 84% 26% / 0.6) 1px, transparent 1px)',
          backgroundSize: '80px 80px',
          maskImage: `radial-gradient(ellipse 50% 50% at ${mousePosition.x * 100}% ${mousePosition.y * 100}%, black 0%, transparent 70%)`,
          WebkitMaskImage: `radial-gradient(ellipse 50% 50% at ${mousePosition.x * 100}% ${mousePosition.y * 100}%, black 0%, transparent 70%)`,
          opacity: 0.4,
        }}
      />
    </div>
  )
}
