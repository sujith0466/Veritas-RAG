import { useEffect, useState } from 'react'
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from 'framer-motion'
import { cn } from '@/utils/cn'

export type AIAssistantState =
  | 'idle'
  | 'greeting'
  | 'email_focus'
  | 'password_focus'
  | 'password_visible'
  | 'loading'
  | 'success'
  | 'error'

interface AIAssistantProps {
  state: AIAssistantState
  className?: string
}

export function AIAssistant({ state, className }: AIAssistantProps) {
  // Parallax tracking
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  // Spring physics for believable mass/weight
  const springConfig = { damping: 30, stiffness: 100, mass: 1.2 }
  const smoothX = useSpring(mouseX, springConfig)
  const smoothY = useSpring(mouseY, springConfig)

  // 3D rotations based on pointer - Agent head tracking
  const rotateX = useTransform(smoothY, [-1, 1], [15, -15])
  const rotateY = useTransform(smoothX, [-1, 1], [-20, 20])

  // Look-at translations for the eyes (creates the impression of active tracking)
  const eyeTrackX = useTransform(smoothX, [-1, 1], [-8, 8])
  const eyeTrackY = useTransform(smoothY, [-1, 1], [-4, 4])

  // Reduced motion support
  const [isReducedMotion, setIsReducedMotion] = useState(false)

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    setIsReducedMotion(mediaQuery.matches)

    const handleMouseMove = (e: MouseEvent) => {
      if (mediaQuery.matches) return
      // Normalize to -1 to 1 based on window
      const x = (e.clientX / window.innerWidth) * 2 - 1
      const y = (e.clientY / window.innerHeight) * 2 - 1
      mouseX.set(x)
      mouseY.set(y)
    }

    const handleMouseLeave = () => {
      if (mediaQuery.matches) return
      mouseX.set(0)
      mouseY.set(0)
    }

    window.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [mouseX, mouseY])

  // Animation variants for the eyes
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const leftEyeVariants: any = {
    idle: { height: 10, width: 10, borderRadius: "50%", backgroundColor: "#94a3b8", rotateZ: 0, transition: { duration: 0.5 } },
    email_focus: { height: 14, width: 14, borderRadius: "50%", backgroundColor: "#64748b", rotateZ: 0, transition: { type: "spring", stiffness: 200 } },
    password_focus: { height: 4, width: 20, borderRadius: "2px", backgroundColor: "#475569", rotateZ: 5, transition: { type: "spring", stiffness: 300 } },
    loading: { height: 4, width: 24, borderRadius: "2px", backgroundColor: "#3b82f6", rotateZ: 0, x: [0, 10, -10, 0], transition: { x: { repeat: Infinity, duration: 1.5, ease: "easeInOut" } } },
    success: { height: 6, width: 24, borderRadius: "3px", backgroundColor: "#10b981", rotateZ: -10, transition: { type: "spring", damping: 12 } },
    error: { height: 4, width: 20, borderRadius: "2px", backgroundColor: "#ef4444", rotateZ: 15, transition: { type: "spring", stiffness: 400, damping: 10 } }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rightEyeVariants: any = {
    idle: { height: 10, width: 10, borderRadius: "50%", backgroundColor: "#94a3b8", rotateZ: 0, transition: { duration: 0.5 } },
    email_focus: { height: 14, width: 14, borderRadius: "50%", backgroundColor: "#64748b", rotateZ: 0, transition: { type: "spring", stiffness: 200 } },
    password_focus: { height: 4, width: 20, borderRadius: "2px", backgroundColor: "#475569", rotateZ: -5, transition: { type: "spring", stiffness: 300 } },
    loading: { height: 4, width: 24, borderRadius: "2px", backgroundColor: "#3b82f6", rotateZ: 0, x: [0, 10, -10, 0], transition: { x: { repeat: Infinity, duration: 1.5, ease: "easeInOut" } } },
    success: { height: 6, width: 24, borderRadius: "3px", backgroundColor: "#10b981", rotateZ: 10, transition: { type: "spring", damping: 12 } },
    error: { height: 4, width: 20, borderRadius: "2px", backgroundColor: "#ef4444", rotateZ: -15, transition: { type: "spring", stiffness: 400, damping: 10 } }
  }

  // Head structural micro-movements
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const headVariants: any = {
    idle: { y: 0, z: 0 },
    email_focus: { y: 2, z: 10, transition: { type: "spring" } },
    password_focus: { y: 4, z: 20, rotateX: 5, transition: { type: "spring" } },
    loading: { y: 0, z: 15, transition: { y: { repeat: Infinity, repeatType: "mirror", duration: 2, ease: "easeInOut" } } },
    success: { y: -5, z: 0, transition: { type: "spring", damping: 10 } },
    error: { y: 2, z: -10, transition: { type: "spring", stiffness: 400, damping: 10 } }
  }

  // Map incoming state to internal animation state
  let animState = state
  if (state === 'password_visible') animState = 'password_focus' // Treat visible similarly to focus for the eyes



  return (
    <div className={cn("relative flex flex-col items-center justify-center w-64 h-64", className)}>
      <motion.div
        style={{
          perspective: 1200,
          rotateX: isReducedMotion ? 0 : rotateX,
          rotateY: isReducedMotion ? 0 : rotateY,
          transformStyle: 'preserve-3d'
        }}
        className="relative w-48 h-48 flex items-center justify-center"
      >
        {/* Ambient Drop Shadow */}
        <motion.div
          className="absolute w-32 h-6 bg-black/5 blur-2xl rounded-[100%]"
          style={{ transform: 'translateY(90px)' }}
          animate={{ scale: state === 'loading' ? 1.1 : 1, opacity: state === 'loading' ? 0.3 : 0.1 }}
        />

        {/* Base / Neck support structure */}
        <div
          className="absolute w-16 h-20 rounded-full bg-gradient-to-b from-slate-200 to-slate-300 border border-white shadow-inner"
          style={{ transform: 'translateZ(-30px) translateY(40px)', transformStyle: 'preserve-3d' }}
        >
          {/* Inner mechanical detail */}
          <div className="absolute inset-x-2 top-4 bottom-2 rounded-full border border-slate-400/30 bg-slate-100/50" />
        </div>

        {/* Main Head Shell */}
        <motion.div
          variants={headVariants}
          initial="idle"
          animate={animState}
          className="absolute w-44 h-32 rounded-[3rem] bg-gradient-to-b from-white via-slate-50 to-slate-200 border border-white flex items-center justify-center overflow-visible"
          style={{
            transformStyle: 'preserve-3d',
            boxShadow: '0 20px 40px rgba(15, 23, 42, 0.08), inset 0 2px 5px rgba(255, 255, 255, 1), inset 0 -10px 20px rgba(15, 23, 42, 0.05)'
          }}
        >
          {/* Structural Seam Lines */}
          <div className="absolute w-full h-[1px] bg-white/60 top-1/2 -translate-y-1/2 shadow-[0_1px_2px_rgba(0,0,0,0.02)] pointer-events-none" />
          <div className="absolute w-[1px] h-full bg-white/60 left-1/2 -translate-x-1/2 shadow-[1px_0_2px_rgba(0,0,0,0.02)] pointer-events-none" />

          {/* Visor Area */}
          <motion.div
            className="absolute w-36 h-16 rounded-[1.5rem] bg-slate-900 overflow-hidden flex items-center justify-center gap-6"
            style={{
              transformStyle: 'preserve-3d',
              z: 20,
              boxShadow: 'inset 0 4px 10px rgba(0,0,0,0.6), inset 0 -2px 5px rgba(255,255,255,0.1), 0 5px 15px rgba(15,23,42,0.1)'
            }}
          >
            {/* Glass reflection */}
            <div className="absolute inset-0 bg-gradient-to-tr from-white/0 via-white/10 to-white/0 pointer-events-none" />
            <div className="absolute top-1 left-4 right-4 h-3 rounded-full bg-gradient-to-b from-white/10 to-transparent pointer-events-none" />

            {/* Eyes Container (Tracks pointer) */}
            <motion.div
              className="flex items-center justify-center gap-6 w-full h-full"
              style={{
                x: isReducedMotion ? 0 : eyeTrackX,
                y: isReducedMotion ? 0 : eyeTrackY,
              }}
            >
              {/* Left Eye */}
              <motion.div
                variants={leftEyeVariants}
                initial="idle"
                animate={animState}
                className="shadow-[0_0_10px_currentColor] relative"
              />

              {/* Right Eye */}
              <motion.div
                variants={rightEyeVariants}
                initial="idle"
                animate={animState}
                className="shadow-[0_0_10px_currentColor] relative"
              />
            </motion.div>

            {/* Scanning line for loading state */}
            <AnimatePresence>
              {state === 'loading' && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 bg-blue-500/10 pointer-events-none"
                >
                  <motion.div
                    className="w-full h-[2px] bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.8)]"
                    animate={{ y: [0, 60, 0] }}
                    transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>

        {/* Floating Semantic Rings (Subtle Architectural Integration) */}
        <motion.div
          className="absolute w-56 h-56 rounded-full border border-slate-200/50 pointer-events-none"
          style={{ transformStyle: 'preserve-3d', z: -20, rotateX: 60 }}
          animate={{ rotateZ: 360 }}
          transition={{ repeat: Infinity, duration: 20, ease: "linear" }}
        >
          <div className="absolute top-0 left-1/2 w-1 h-1 bg-slate-300 rounded-full -translate-x-1/2 -translate-y-1/2" />
        </motion.div>
      </motion.div>
    </div>
  )
}
