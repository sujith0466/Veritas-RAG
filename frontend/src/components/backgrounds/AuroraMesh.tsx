import { memo } from 'react'
import { cn } from '@/utils/cn'

interface AuroraMeshProps {
  className?: string
}

export const AuroraMesh = memo(function AuroraMesh({ className }: AuroraMeshProps) {
  return (
    <div
      className={cn(
        'pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background',
        className,
      )}
    >
      {/* Static, subtle ambient gradient: light theme preserves soft neutral ambient, dark theme aligns with brand teal */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.04),transparent_60%)] dark:bg-[radial-gradient(ellipse_at_top,rgba(69,175,162,0.06),transparent_60%)]" />
    </div>
  )
})
