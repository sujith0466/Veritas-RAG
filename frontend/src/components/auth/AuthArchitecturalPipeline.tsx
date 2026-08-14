import { useEffect } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion'

// SVG-based Internal Structure for perfectly crisp, abstract architectural details
// Reused from ArchitecturalPipeline but visually subdued for auth background
function BlueprintDetails({ layerId }: { layerId: string }) {
  if (layerId === 'evidence') {
    return (
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />
        <rect x="10%" y="20%" width="30%" height="10%" fill="none" stroke="currentColor" strokeWidth="1" />
        <rect x="45%" y="20%" width="10%" height="10%" fill="none" stroke="currentColor" strokeWidth="1" />
        <rect x="60%" y="20%" width="30%" height="10%" fill="none" stroke="currentColor" strokeWidth="1" />
        <line x1="0" y1="40%" x2="100%" y2="40%" stroke="currentColor" strokeWidth="0.5" strokeDasharray="4 4" />
        <rect x="10%" y="50%" width="80%" height="4%" fill="currentColor" />
        <rect x="10%" y="60%" width="60%" height="4%" fill="currentColor" opacity="0.5" />
        <rect x="10%" y="70%" width="40%" height="4%" fill="currentColor" opacity="0.3" />
        <circle cx="5%" cy="5%" r="2" fill="currentColor" />
        <circle cx="95%" cy="5%" r="2" fill="currentColor" />
        <circle cx="5%" cy="95%" r="2" fill="currentColor" />
        <circle cx="95%" cy="95%" r="2" fill="currentColor" />
      </svg>
    )
  }

  if (layerId === 'validation') {
    return (
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
        <line x1="20%" y1="0" x2="20%" y2="100%" stroke="currentColor" strokeWidth="1" />
        <line x1="80%" y1="0" x2="80%" y2="100%" stroke="currentColor" strokeWidth="1" />
        <line x1="30%" y1="20%" x2="70%" y2="20%" stroke="currentColor" strokeWidth="1" />
        <line x1="70%" y1="20%" x2="55%" y2="80%" stroke="currentColor" strokeWidth="1" />
        <line x1="55%" y1="80%" x2="45%" y2="80%" stroke="currentColor" strokeWidth="1" />
        <line x1="45%" y1="80%" x2="30%" y2="20%" stroke="currentColor" strokeWidth="1" />
        <line x1="35%" y1="30%" x2="65%" y2="30%" stroke="currentColor" strokeWidth="0.5" />
        <line x1="40%" y1="50%" x2="60%" y2="50%" stroke="currentColor" strokeWidth="0.5" />
        <line x1="43%" y1="70%" x2="57%" y2="70%" stroke="currentColor" strokeWidth="0.5" />
        <line x1="0" y1="50%" x2="10%" y2="50%" stroke="currentColor" strokeWidth="1" />
        <line x1="90%" y1="50%" x2="100%" y2="50%" stroke="currentColor" strokeWidth="1" />
      </svg>
    )
  }

  if (layerId === 'reliability') {
    return (
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
        <rect x="20%" y="20%" width="60%" height="50%" fill="none" stroke="currentColor" strokeWidth="1" />
        <line x1="20%" y1="70%" x2="80%" y2="70%" stroke="currentColor" strokeWidth="1" />
        <line x1="20%" y1="20%" x2="20%" y2="70%" stroke="currentColor" strokeWidth="1" />
        <rect x="25%" y="60%" width="8%" height="10%" fill="currentColor" />
        <rect x="38%" y="45%" width="8%" height="25%" fill="currentColor" />
        <rect x="51%" y="30%" width="8%" height="40%" fill="currentColor" />
        <rect x="64%" y="50%" width="8%" height="20%" fill="currentColor" />
        <line x1="0" y1="30%" x2="100%" y2="30%" stroke="currentColor" strokeWidth="0.5" strokeDasharray="2 6" />
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="currentColor" strokeWidth="0.5" strokeDasharray="2 6" />
      </svg>
    )
  }

  if (layerId === 'answer') {
    return (
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" xmlns="http://www.w3.org/2000/svg">
        <rect x="25%" y="15%" width="50%" height="60%" fill="none" stroke="currentColor" strokeWidth="1" />
        <rect x="30%" y="25%" width="15%" height="3%" fill="currentColor" />
        <rect x="30%" y="35%" width="40%" height="1%" fill="currentColor" />
        <rect x="30%" y="42%" width="35%" height="1%" fill="currentColor" />
        <rect x="30%" y="49%" width="38%" height="1%" fill="currentColor" />
        <rect x="30%" y="56%" width="20%" height="1%" fill="currentColor" />
        <circle cx="50%" cy="50%" r="3" fill="none" stroke="currentColor" strokeWidth="1" />
        <line x1="45%" y1="50%" x2="55%" y2="50%" stroke="currentColor" strokeWidth="0.5" />
        <line x1="50%" y1="45%" x2="50%" y2="55%" stroke="currentColor" strokeWidth="0.5" />
      </svg>
    )
  }

  return null
}

export function AuthArchitecturalPipeline() {
  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  // Extremely subtle, smooth springs for mouse movement
  const springConfig = { damping: 60, stiffness: 80, mass: 2 }
  const springX = useSpring(mouseX, springConfig)
  const springY = useSpring(mouseY, springConfig)

  // Reduced parallax effect for Auth background
  const parallaxX = useTransform(springY, [-1, 1], [1, -1])
  const parallaxY = useTransform(springX, [-1, 1], [-1.5, 1.5])

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')

    const handleMouseMove = (e: MouseEvent) => {
      if (mediaQuery.matches) return

      const { innerWidth, innerHeight } = window
      const x = (e.clientX / innerWidth) * 2 - 1
      const y = (e.clientY / innerHeight) * 2 - 1

      mouseX.set(x)
      mouseY.set(y)
    }

    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [mouseX, mouseY])

  // Flat perspective for auth (behind the card)
  const baseRotateX = 15
  const baseRotateY = -15

  const finalRotateX = useTransform(parallaxX, r => r + baseRotateX)
  const finalRotateY = useTransform(parallaxY, r => r + baseRotateY)

  // Reduced z-depth spacing to keep it tightly packed behind the auth form
  const layers = [
    { id: 'evidence', label: 'Evidence Layer', z: -150 },
    { id: 'validation', label: 'Validation Layer', z: -50 },
    { id: 'reliability', label: 'Reliability Layer', z: 50 },
    { id: 'answer', label: 'Answer Layer', z: 150 },
  ]

  return (
    <div
      className="absolute inset-0 overflow-hidden pointer-events-none flex items-center justify-center bg-background"
      style={{ perspective: '1200px' }}
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-noise opacity-[0.015] mix-blend-multiply pointer-events-none z-0" />
      
      <motion.div
        className="relative w-[120vw] h-[80vw] max-w-[1200px] max-h-[800px] z-0 opacity-[0.65]"
        style={{
          transformStyle: 'preserve-3d',
          rotateX: finalRotateX,
          rotateY: finalRotateY,
        }}
      >
        {/* Core architectural connection line passing through the center of all planes */}
        <div
          className="absolute top-1/2 left-1/2 w-px h-[400px] bg-slate-400/20"
          style={{
            transform: 'translate(-50%, -50%) rotateX(90deg)',
          }}
        />

        {/* Primary Pipeline Panels */}
        {layers.map((layer, index) => (
          <motion.div
            key={layer.id}
            className="absolute inset-0 flex flex-col justify-end rounded-[32px]"
            style={{
              translateZ: layer.z,
              // Lighter glass effect
              background: 'rgba(252, 252, 252, 0.35)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
              // Extremely subtle edge lighting
              border: '1px solid rgba(148, 163, 184, 0.15)',
              borderTopColor: 'rgba(255, 255, 255, 0.6)',
              borderLeftColor: 'rgba(255, 255, 255, 0.4)',
              boxShadow: '0 16px 32px -8px rgba(15, 23, 42, 0.04)',
              color: '#0f172a' 
            }}
          >
            <BlueprintDetails layerId={layer.id} />
            <div className="p-6 flex items-center space-x-3 opacity-50 border-t border-slate-900/[0.04] relative z-10">
              <span className="text-[10px] font-mono tracking-[0.2em] text-slate-400 uppercase">
                0{index + 1}
              </span>
              <span className="text-xs font-medium text-slate-700 tracking-wide">
                {layer.label}
              </span>
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Subtle top/bottom masking gradients to keep focus on center auth card */}
      <div className="absolute inset-0 bg-gradient-to-b from-background via-transparent to-background opacity-40 z-10" />
    </div>
  )
}
