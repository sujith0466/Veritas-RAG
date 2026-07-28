import { motion } from 'framer-motion'
import { useEffect, useState } from 'react'

export function FloatingBackground() {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
      })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  return (
    <div className="fixed inset-0 overflow-hidden bg-background z-[-1] pointer-events-none">
      {/* Premium gradient base */}
      <div className="absolute inset-0 bg-gradient-to-br from-background via-primary/5 to-surface-elevated/20" />
      
      {/* Aurora gradients */}
      <motion.div
        animate={{
          x: mousePosition.x * 60 - 30,
          y: mousePosition.y * 60 - 30,
        }}
        transition={{ type: 'spring', damping: 50, stiffness: 100 }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] rounded-full bg-primary/10 blur-[120px] mix-blend-screen opacity-50 pointer-events-none"
      />
      <motion.div
        animate={{
          x: mousePosition.x * -80 + 40,
          y: mousePosition.y * -80 + 40,
        }}
        transition={{ type: 'spring', damping: 50, stiffness: 100 }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[50vw] h-[50vw] rounded-full bg-blue-500/10 blur-[120px] mix-blend-screen opacity-40 pointer-events-none"
      />
      
      {/* Moving light streaks */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 150, repeat: Infinity, ease: 'linear' }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[150vw] h-[150vw] opacity-30"
      >
        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-gradient-to-b from-transparent via-primary/30 to-transparent transform -translate-x-1/2" />
        <div className="absolute left-0 right-0 top-1/2 h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent transform -translate-y-1/2" />
      </motion.div>
      
      {/* Premium noise texture overlay */}
      <div 
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")',
        }}
      />
    </div>
  )
}
