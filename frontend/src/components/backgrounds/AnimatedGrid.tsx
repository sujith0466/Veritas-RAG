import { memo } from 'react'
import { cn } from '@/utils/cn'

interface AnimatedGridProps {
  className?: string
}

export const AnimatedGrid = memo(function AnimatedGrid({ className }: AnimatedGridProps) {
  return (
    <div
      className={cn(
        'pointer-events-none fixed inset-0 -z-10 flex h-full w-full justify-center',
        className,
      )}
    >
      <div className="absolute inset-0 bg-background" />
      <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--border-subtle))_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--border-subtle))_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] opacity-20" />
      
      {/* Subtle floating glow orb */}
      <div className="absolute -top-40 left-1/2 h-[40rem] w-[40rem] -translate-x-1/2 rounded-full bg-primary/5 blur-[120px] animate-pulse-subtle" />
    </div>
  )
})
