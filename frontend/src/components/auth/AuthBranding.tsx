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

export interface AuthBrandingProps {
  className?: string
  /**
   * 'logo': Horizontal brand lockup (primary logo in light mode, dark icon + wordmark in dark mode)
   * 'icon': Compact app icon symbol (light icon in light mode, dark icon in dark mode)
   * 'auto': Defaults to 'logo'
   */
  variant?: 'logo' | 'icon' | 'auto'
  /**
   * Interactive/form state preserved for backward compatibility
   */
  state?: AIAssistantState
}

export function AuthBranding({
  className,
  variant = 'logo',
  state = 'idle',
}: AuthBrandingProps) {
  const isIconOnly = variant === 'icon'
  const isLoading = state === 'loading'
  const isError = state === 'error'
  const isSuccess = state === 'success'

  return (
    <div
      data-testid="auth-branding"
      className={cn(
        'relative flex items-center justify-center transition-all duration-300 ease-out select-none',
        isLoading && 'opacity-80 animate-pulse',
        isError && 'ring-1 ring-danger/40 rounded-2xl p-1',
        isSuccess && 'ring-1 ring-success/40 rounded-2xl p-1',
        className
      )}
    >
      {isIconOnly ? (
        <div className="relative flex items-center justify-center transition-transform duration-300 ease-out hover:scale-105 motion-reduce:transform-none">
          {/* Light Theme: Compact light app icon */}
          <img
            src="/veritas-rag-icon-light.png"
            alt="Veritas RAG"
            className="h-12 w-12 sm:h-14 sm:w-14 rounded-2xl object-contain shadow-sm border border-border/50 dark:hidden"
            loading="eager"
            draggable={false}
          />

          {/* Dark Theme: Compact dark app icon */}
          <img
            src="/veritas-rag-icon-dark.png"
            alt="Veritas RAG"
            className="h-12 w-12 sm:h-14 sm:w-14 rounded-2xl object-contain shadow-sm border border-border/50 hidden dark:block"
            loading="eager"
            draggable={false}
          />
        </div>
      ) : (
        <div className="relative flex items-center justify-center transition-transform duration-300 ease-out hover:scale-[1.02] motion-reduce:transform-none">
          {/* Light Theme: Primary brand logo with wordmark */}
          <img
            src="/veritas-rag-logo.png"
            alt="Veritas RAG"
            className="h-10 sm:h-12 w-auto max-w-[200px] sm:max-w-[220px] object-contain dark:hidden"
            loading="eager"
            draggable={false}
          />

          {/* Dark Theme: Dark icon paired with crisp enterprise typography */}
          <div className="hidden dark:flex items-center gap-2.5">
            <img
              src="/veritas-rag-icon-dark.png"
              alt="Veritas RAG"
              className="h-9 w-9 sm:h-10 sm:w-10 rounded-xl object-contain shadow-sm border border-border/50"
              loading="eager"
              draggable={false}
            />
            <span className="text-xl sm:text-2xl font-bold tracking-tight text-foreground font-sans">
              Veritas RAG
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
