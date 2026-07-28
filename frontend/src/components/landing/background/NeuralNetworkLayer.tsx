import { useMemo, useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

function seededRandom(seed: number) {
  const x = Math.sin(seed + 1) * 10000
  return x - Math.floor(x)
}

interface Node {
  id: number
  x: number
  y: number
}

interface Connection {
  id: string
  from: Node
  to: Node
}

/**
 * NeuralNetworkLayer — a subtle animated SVG showing interconnected data nodes.
 * Uses a seeded layout so nodes don't re-randomize on every render.
 * Reacts to mouse movement for a parallax effect.
 * Tuned for the light theme: stronger stroke and fill opacities.
 */
export function NeuralNetworkLayer() {
  const shouldReduceMotion = useReducedMotion()
  const [mouseOffset, setMouseOffset] = useState({ x: 0, y: 0 })
  const [pulse, setPulse] = useState(0)

  // Deterministic stable node layout
  const { nodes, connections } = useMemo(() => {
    const nodeList: Node[] = Array.from({ length: 30 }).map((_, i) => ({
      id: i,
      x: seededRandom(i * 3 + 1) * 85 + 7.5,   // 7.5–92.5%
      y: seededRandom(i * 7 + 2) * 85 + 7.5,   // 7.5–92.5%
    }))

    const connectionList: Connection[] = []
    for (let i = 0; i < nodeList.length; i++) {
      for (let j = i + 1; j < nodeList.length; j++) {
        const dx = nodeList[i].x - nodeList[j].x
        const dy = nodeList[i].y - nodeList[j].y
        if (Math.sqrt(dx * dx + dy * dy) < 22) {
          connectionList.push({ from: nodeList[i], to: nodeList[j], id: `${i}-${j}` })
        }
      }
    }

    return { nodes: nodeList, connections: connectionList }
  }, [])

  // Mouse parallax
  useEffect(() => {
    if (shouldReduceMotion) return
    const handleMove = (e: MouseEvent) => {
      setMouseOffset({
        x: (e.clientX / window.innerWidth - 0.5) * -25,
        y: (e.clientY / window.innerHeight - 0.5) * -25,
      })
    }
    window.addEventListener('mousemove', handleMove)
    return () => window.removeEventListener('mousemove', handleMove)
  }, [shouldReduceMotion])

  // Pulse one node at a time
  useEffect(() => {
    if (shouldReduceMotion) return
    const id = setInterval(() => setPulse((p) => (p + 1) % nodes.length), 800)
    return () => clearInterval(id)
  }, [shouldReduceMotion, nodes.length])

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none z-[1]">
      <motion.svg
        className="w-full h-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid slice"
        animate={shouldReduceMotion ? {} : { x: mouseOffset.x, y: mouseOffset.y }}
        transition={{ type: 'spring', stiffness: 40, damping: 20 }}
        style={{ overflow: 'visible' }}
      >
        {/* Connections */}
        {connections.map((c) => (
          <line
            key={c.id}
            x1={`${c.from.x}%`}
            y1={`${c.from.y}%`}
            x2={`${c.to.x}%`}
            y2={`${c.to.y}%`}
            stroke="hsl(175 84% 26%)"
            strokeWidth="0.15"
            opacity="0.25"
          />
        ))}

        {/* Nodes */}
        {nodes.map((n, i) => {
          const isActive = i === pulse
          return (
            <g key={n.id}>
              {/* Glow ring on active node */}
              {isActive && (
                <motion.circle
                  cx={`${n.x}%`}
                  cy={`${n.y}%`}
                  r="1.2"
                  fill="none"
                  stroke="hsl(175 84% 26%)"
                  strokeWidth="0.4"
                  opacity="0.6"
                  initial={{ scale: 1, opacity: 0.6 }}
                  animate={{ scale: 3, opacity: 0 }}
                  transition={{ duration: 1.2, ease: 'easeOut' }}
                />
              )}
              <circle
                cx={`${n.x}%`}
                cy={`${n.y}%`}
                r={isActive ? '0.9' : '0.5'}
                fill="hsl(175 84% 26%)"
                opacity={isActive ? 0.8 : 0.3}
              />
            </g>
          )
        })}
      </motion.svg>
    </div>
  )
}
