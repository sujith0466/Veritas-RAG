import { cn } from '@/utils/cn'

interface VoiceVisualizerProps {
  volumes: number[]
  isListening: boolean
  className?: string
}

export function VoiceVisualizer({ volumes, isListening, className }: VoiceVisualizerProps) {
  // Ensure we have at least 5 bar values
  const bars = volumes.length >= 5 ? volumes.slice(0, 5) : [0.2, 0.4, 0.6, 0.4, 0.2]

  return (
    <div
      className={cn('flex items-center gap-1 px-2 py-1', className)}
      aria-hidden="true"
      title="Voice activity visualizer"
    >
      {bars.map((vol, idx) => {
        // Height scaled between 4px (0.1) and 20px (1.0)
        const heightPx = Math.max(4, Math.round(vol * 22))

        return (
          <span
            key={idx}
            style={{ height: `${heightPx}px` }}
            className={cn(
              'w-1 rounded-full transition-[height] duration-100 ease-out',
              isListening
                ? 'bg-emerald-500 dark:bg-emerald-400'
                : 'bg-muted-foreground/40'
            )}
          />
        )
      })}
    </div>
  )
}
