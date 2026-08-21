import { useAppStore } from '@/stores/appStore'

export function Footer() {
  const version = useAppStore((state) => state.appVersion)

  return (
    <footer className="mt-auto border-t border-border bg-surface/50 px-6 py-4 backdrop-blur-md">
      <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-success animate-pulse-subtle" />
          <p className="text-xs text-muted-foreground">
            Systems Operational
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} Veritas RAG. All rights reserved.</span>
          <span className="hidden sm:inline">|</span>
          <span className="hidden sm:inline">v{version}</span>
        </div>
      </div>
    </footer>
  )
}
