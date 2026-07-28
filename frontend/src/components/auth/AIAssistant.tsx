import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/utils/cn'
import { useEffect, useState } from 'react'
import { Shield } from 'lucide-react'

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
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 })

  // Subtle loading state text rotation
  const [loadingText, setLoadingText] = useState('Verifying credentials...')
  useEffect(() => {
    if (state === 'loading') {
      const t1 = setTimeout(() => setLoadingText('Establishing secure session...'), 3000)
      const t2 = setTimeout(() => setLoadingText('Preparing your workspace...'), 6000)
      return () => { clearTimeout(t1); clearTimeout(t2) }
    } else {
      setLoadingText('Verifying credentials...')
    }
  }, [state])

  // Cursor tracking
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (state === 'password_focus') return // Ignore tracking when in privacy mode
      setMousePosition({
        x: (e.clientX / window.innerWidth) * 2 - 1,
        y: (e.clientY / window.innerHeight) * 2 - 1
      })
    }
    const handleMouseLeave = () => setMousePosition({ x: 0, y: 0 })
    window.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseleave', handleMouseLeave)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [state])

  const isPrivacy = state === 'password_focus'
  const isScanning = state === 'loading'
  const isSuccess = state === 'success'

  const speechMap: Record<string, string> = {
    idle: '',
    greeting: 'Welcome to RAGuard AI.',
    email_focus: 'Welcome back.',
    password_focus: 'Your password stays private.',
    password_visible: 'Password visible.',
    loading: loadingText,
    success: 'Welcome back!',
    error: 'Connection issue. Let\'s try again.'
  }

  // Animation values mapped heavily to state
  const eyeVariants = {
    idle: { height: 16, borderRadius: '20px', scaleY: [1, 0.1, 1], transition: { scaleY: { repeat: Infinity, duration: 4, times: [0, 0.05, 0.1] } } },
    greeting: { height: 18, borderRadius: '40% 40% 20% 20%', scaleY: 1 },
    email_focus: { height: 16, borderRadius: '20px', scaleY: 1, x: 5, y: 2 },
    password_focus: { height: 2, borderRadius: '20px', scaleY: 0.1, x: 0, y: 0 },
    password_visible: { height: 16, borderRadius: '20px', scaleY: 1, x: -5, y: 2 },
    loading: { height: 6, width: 40, borderRadius: '4px', scaleX: [1, 1.5, 1], backgroundColor: '#38bdf8', transition: { repeat: Infinity, duration: 1.5 } }, // Visor
    success: { height: 20, borderRadius: '50% 50% 10% 10%', scaleY: [1, 0.9, 1], backgroundColor: '#34d399', transition: { scaleY: { repeat: Infinity, duration: 2 } } },
    error: { height: 12, borderRadius: '20% 20% 40% 40%', backgroundColor: '#f87171', rotate: [0, -10, 10, -10, 0], transition: { duration: 0.5 } }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any

  // Body container animation (floating, rotation)
  const coreVariants = {
    idle: { y: [0, -8, 0], rotateX: mousePosition.y * -10, rotateY: mousePosition.x * 10, transition: { y: { repeat: Infinity, duration: 4, ease: 'easeInOut' } } },
    password_focus: { y: 5, rotateY: -15, rotateX: 5, transition: { duration: 0.6 } },
    password_visible: { y: [0, -5, 0], rotateX: mousePosition.y * -10, rotateY: mousePosition.x * 10, transition: { duration: 0.6 } },
    loading: { y: [0, -3, 0], rotateY: [0, 360], transition: { y: { repeat: Infinity, duration: 0.5 }, rotateY: { repeat: Infinity, duration: 8, ease: 'linear' } } },
    success: { y: [0, -15, 0], rotateY: [0, 360], transition: { y: { repeat: Infinity, duration: 2, ease: 'easeInOut' }, rotateY: { duration: 1 } } },
    error: { x: [-5, 5, -5, 5, 0], rotateY: 0, transition: { duration: 0.4 } },
    default: { y: 0, rotateX: mousePosition.y * -10, rotateY: mousePosition.x * 10, transition: { type: 'spring' } }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } as any

  // Glow colors
  const colorMap: Record<string, string> = {
    idle: 'rgba(59, 130, 246, 0.3)',
    greeting: 'rgba(139, 92, 246, 0.4)',
    email_focus: 'rgba(59, 130, 246, 0.4)',
    password_focus: 'rgba(71, 85, 105, 0.5)',
    password_visible: 'rgba(245, 158, 11, 0.4)',
    loading: 'rgba(14, 165, 233, 0.6)',
    success: 'rgba(16, 185, 129, 0.6)',
    error: 'rgba(239, 68, 68, 0.5)'
  }

  const activeColor = colorMap[state] || colorMap.idle

  return (
    <div className={cn("relative flex flex-col items-center justify-center h-56 w-56 perspective-1000", className)}>
      
      {/* Speech Bubble */}
      <AnimatePresence mode="wait">
        {speechMap[state] && (
          <motion.div
            key={speechMap[state]}
            initial={{ opacity: 0, y: 15, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.9 }}
            transition={{ type: 'spring', damping: 20 }}
            className="absolute -top-16 px-4 py-2 bg-surface-elevated/90 backdrop-blur-xl rounded-2xl border border-white/20 text-xs font-semibold text-foreground whitespace-nowrap shadow-2xl z-40"
          >
            {speechMap[state]}
            <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-surface-elevated/90 border-b border-r border-white/20 rotate-45 backdrop-blur-xl" />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        variants={coreVariants}
        initial="idle"
        animate={['password_focus', 'password_visible', 'loading', 'success', 'error'].includes(state) ? state : 'default'}
        style={{ transformStyle: 'preserve-3d' }}
        className="relative flex items-center justify-center w-28 h-28 z-20"
      >
        {/* Holographic Rings (Outer) */}
        <motion.div
          animate={{ 
            rotateX: isPrivacy ? 80 : 60, 
            rotateZ: [0, 360], 
            scale: isScanning ? 1.4 : isSuccess ? [1, 1.3, 1] : 1.1,
            borderColor: isScanning ? 'rgba(56, 189, 248, 0.6)' : isSuccess ? 'rgba(52, 211, 153, 0.5)' : 'rgba(59, 130, 246, 0.2)'
          }}
          transition={{ rotateZ: { repeat: Infinity, duration: isScanning ? 2 : 12, ease: 'linear' }, scale: { duration: 1 } }}
          style={{ transformStyle: 'preserve-3d' }}
          className="absolute inset-[-25%] border-[2px] rounded-full z-0"
        />
        
        {/* Inner Ring */}
        <motion.div
          animate={{ 
            rotateX: isPrivacy ? 60 : 75, 
            rotateZ: [360, 0], 
            scale: isScanning ? 1.2 : 0.9,
            borderColor: isScanning ? 'rgba(56, 189, 248, 0.4)' : 'rgba(255, 255, 255, 0.1)'
          }}
          transition={{ rotateZ: { repeat: Infinity, duration: 8, ease: 'linear' } }}
          style={{ transformStyle: 'preserve-3d' }}
          className="absolute inset-[-35%] border-[1px] border-dashed rounded-full z-0"
        />

        {/* Ambient Volumetric Glow */}
        <motion.div 
          animate={{ backgroundColor: activeColor }}
          transition={{ duration: 0.5 }}
          className="absolute inset-[-50%] blur-3xl opacity-40 rounded-full z-0 pointer-events-none"
        />

        {/* Main Ceramic Shell */}
        <motion.div 
          className="w-full h-full rounded-[45%] bg-white/95 backdrop-blur-3xl relative overflow-hidden flex items-center justify-center shadow-2xl z-10"
          style={{ 
            boxShadow: `inset 0px -15px 30px rgba(0,0,0,0.1), inset 0px 10px 20px rgba(255,255,255,0.8), 0 20px 40px ${activeColor}`,
            border: '1px solid rgba(255,255,255,0.6)'
          }}
        >
          {/* Internal Energy Core */}
          <motion.div 
            className="absolute inset-0 opacity-60 mix-blend-overlay"
            animate={{ background: `radial-gradient(circle at ${50 + mousePosition.x * 20}% ${40 + mousePosition.y * 20}%, ${activeColor}, transparent 80%)` }}
            transition={{ duration: 0.2 }}
          />

          {/* Glass Visor / Face Area */}
          <motion.div 
            className="absolute w-[80%] h-[60%] rounded-[30px] bg-black/80 shadow-inner overflow-hidden flex items-center justify-center"
            style={{ boxShadow: 'inset 0 10px 20px rgba(0,0,0,0.8), 0 2px 10px rgba(255,255,255,0.2)' }}
            animate={{
              x: mousePosition.x * 8,
              y: mousePosition.y * 8
            }}
          >
            {/* Display Glare */}
            <div className="absolute top-0 left-0 right-0 h-1/2 bg-gradient-to-b from-white/10 to-transparent rounded-t-[30px] pointer-events-none" />

            {/* Scanning Visor (Loading State) */}
            <AnimatePresence>
              {isScanning && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 flex items-center justify-center"
                >
                  <motion.div 
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    variants={eyeVariants as any}
                    initial="idle"
                    animate="loading"
                  />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Standard Eyes */}
            <AnimatePresence>
              {!isScanning && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="relative w-12 h-6 flex justify-between items-center z-10"
                >
                  <motion.div
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    variants={eyeVariants as any}
                    initial="idle"
                    animate={state}
                    className="w-4 bg-white shadow-[0_0_10px_rgba(255,255,255,0.8)]"
                  />
                  <motion.div
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    variants={eyeVariants as any}
                    initial="idle"
                    animate={state}
                    className="w-4 bg-white shadow-[0_0_10px_rgba(255,255,255,0.8)]"
                  />
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </motion.div>

        {/* Privacy Mode Hands (3D layering) */}
        <AnimatePresence>
          {isPrivacy && (
            <motion.div
              initial={{ opacity: 0, y: 40, scale: 0.8, rotateX: 45 }}
              animate={{ opacity: 1, y: -5, scale: 1, rotateX: 0 }}
              exit={{ opacity: 0, y: 40, scale: 0.8, rotateX: 45 }}
              transition={{ type: 'spring', damping: 15, stiffness: 100 }}
              className="absolute inset-0 flex justify-center items-center z-30 pointer-events-none"
              style={{ transformStyle: 'preserve-3d', perspective: '500px' }}
            >
              <div className="relative w-[120%] h-full flex justify-between items-center px-2">
                {/* Left Hand */}
                <motion.div 
                  className="w-10 h-14 bg-white/95 backdrop-blur-xl rounded-full shadow-[0_10px_20px_rgba(0,0,0,0.3),inset_-2px_-5px_10px_rgba(0,0,0,0.1)] border border-white/40"
                  animate={{ rotateZ: -25, rotateY: 15, x: 10, y: 5 }}
                />
                {/* Right Hand */}
                <motion.div 
                  className="w-10 h-14 bg-white/95 backdrop-blur-xl rounded-full shadow-[0_10px_20px_rgba(0,0,0,0.3),inset_2px_-5px_10px_rgba(0,0,0,0.1)] border border-white/40"
                  animate={{ rotateZ: 25, rotateY: -15, x: -10, y: 5 }}
                />
              </div>
              
              {/* Privacy Shield Icon Glow */}
              <motion.div 
                initial={{ opacity: 0, scale: 0 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 }}
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-primary/80 z-40 drop-shadow-[0_0_10px_rgba(59,130,246,0.8)]"
              >
                <Shield className="w-8 h-8" />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
        
        {/* Success Hand Wave */}
        <AnimatePresence>
          {isSuccess && (
            <motion.div
              initial={{ opacity: 0, y: 20, x: 40, rotateZ: 0 }}
              animate={{ opacity: 1, y: -10, x: 45, rotateZ: [0, 20, -10, 20, 0] }}
              exit={{ opacity: 0, y: 20, x: 40 }}
              transition={{ duration: 1.5 }}
              className="absolute inset-0 flex items-center z-30 pointer-events-none"
            >
              <div className="w-8 h-12 bg-white/95 backdrop-blur-xl rounded-full shadow-[0_10px_20px_rgba(0,0,0,0.3)] border border-white/40" />
            </motion.div>
          )}
        </AnimatePresence>

      </motion.div>

      {/* Hover Shadow underneath */}
      <motion.div
        animate={{ 
          scale: isSuccess ? [1, 0.8, 1] : isScanning ? [1, 0.9, 1] : [1, 1.2, 1],
          opacity: isSuccess ? [0.6, 0.3, 0.6] : [0.5, 0.2, 0.5]
        }}
        transition={{ repeat: Infinity, duration: isSuccess ? 2 : isScanning ? 0.5 : 4, ease: 'easeInOut' }}
        className="absolute -bottom-6 w-20 h-4 bg-black/40 blur-xl rounded-[100%] z-0"
      />
      
      {/* Ambient particles for success */}
      <AnimatePresence>
        {isSuccess && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-0 pointer-events-none"
          >
            {[...Array(6)].map((_, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
                animate={{ 
                  opacity: [0, 1, 0], 
                  scale: [0, 1.5, 0], 
                  x: (Math.random() - 0.5) * 150, 
                  y: (Math.random() - 0.5) * 150 - 50 
                }}
                transition={{ duration: 1.5, delay: i * 0.1 }}
                className="absolute top-1/2 left-1/2 w-2 h-2 bg-emerald-400 rounded-full blur-[1px] shadow-[0_0_10px_rgba(52,211,153,0.8)]"
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
