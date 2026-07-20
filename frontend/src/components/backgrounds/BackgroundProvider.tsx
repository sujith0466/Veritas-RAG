import { AuroraMesh } from './AuroraMesh'
import { AnimatedGrid } from './AnimatedGrid'
import { useMediaQuery } from '@/hooks/useMediaQuery'

type BackgroundType = 'aurora' | 'grid' | 'none'

interface BackgroundProviderProps {
  type?: BackgroundType
}

export function BackgroundProvider({ type = 'aurora' }: BackgroundProviderProps) {
  const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

  if (type === 'none' || prefersReducedMotion) {
    return <div className="pointer-events-none fixed inset-0 -z-10 bg-background" />
  }

  return (
    <>
      {type === 'aurora' && <AuroraMesh />}
      {type === 'grid' && <AnimatedGrid />}
    </>
  )
}
