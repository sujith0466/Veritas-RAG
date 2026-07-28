import { motion, useReducedMotion } from 'framer-motion'

/**
 * AmbientGradient — very soft, subtle radial gradients for a premium minimal background.
 * Opacities are kept extremely low (2-4%) so they don't distract from hero content.
 */
export function AmbientGradient() {
  const shouldReduceMotion = useReducedMotion()

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-0">
      {/* Very soft teal glow — top left */}
      <motion.div
        animate={
          shouldReduceMotion
            ? { opacity: 0.03 }
            : {
                opacity: [0.02, 0.04, 0.02],
                scale: [1, 1.05, 1],
                x: [0, 15, 0],
                y: [0, -15, 0],
              }
        }
        transition={{ duration: 25, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute -top-[10%] -left-[5%] w-[60vw] h-[60vh] rounded-full blur-[120px]"
        style={{ background: 'hsl(175 84% 26%)' }}
      />

      {/* Very soft blue/indigo glow — bottom right */}
      <motion.div
        animate={
          shouldReduceMotion
            ? { opacity: 0.02 }
            : {
                opacity: [0.015, 0.035, 0.015],
                scale: [1, 1.08, 1],
                x: [0, -20, 0],
                y: [0, 20, 0],
              }
        }
        transition={{ duration: 30, repeat: Infinity, ease: 'easeInOut', delay: 4 }}
        className="absolute -bottom-[10%] -right-[5%] w-[60vw] h-[60vh] rounded-full blur-[140px]"
        style={{ background: 'hsl(245 60% 55%)' }}
      />
    </div>
  )
}
