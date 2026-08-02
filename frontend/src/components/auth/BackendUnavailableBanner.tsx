import { useState, useEffect } from 'react'
import { ServerCrash, RefreshCw } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'
import { Button } from '@/components/common/Button'
import { PageTransition } from '@/components/layouts'

export function BackendUnavailableBanner() {
  const [isRetrying, setIsRetrying] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const { token, setAuth, error } = useAuthStore()

  // Auto-retry polling every 15 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      handleRetry()
    }, 15000)
    return () => clearInterval(interval)
  }, [token])

  const handleRetry = async () => {
    if (isRetrying || !token) return
    setIsRetrying(true)
    setErrorMsg(null)

    try {
      // fetchBackendProfile will retry 3 times internally
      const userContext = await authService.fetchBackendProfile()
      // If it succeeds, setAuth will clear the error state and transition to AUTHENTICATED
      setAuth(userContext, token)
    } catch (err: unknown) {
      setErrorMsg('Still unable to connect to the server. Will keep trying.')
    } finally {
      setIsRetrying(false)
    }
  }

  return (
    <PageTransition>
      <div className="flex h-screen w-full flex-col items-center justify-center bg-background text-center p-8 space-y-6">
        <div className="h-20 w-20 rounded-full bg-danger/10 flex items-center justify-center animate-pulse">
          <ServerCrash className="h-10 w-10 text-danger" />
        </div>

        <div className="space-y-2 max-w-md">
          <h2 className="text-2xl font-bold text-foreground">Service Temporarily Unavailable</h2>
          <p className="text-muted-foreground">
            {error?.message || 'We securely verified your identity, but we are unable to load your workspace profile right now. The backend services may be starting up or experiencing high load.'}
          </p>
        </div>

        {errorMsg && (
          <div className="text-sm text-danger font-medium bg-danger/10 px-4 py-2 rounded-md">
            {errorMsg}
          </div>
        )}

        <Button
          variant="default"
          size="lg"
          onClick={handleRetry}
          isLoading={isRetrying}
          className="mt-8"
        >
          <RefreshCw className={`h-5 w-5 mr-2 ${isRetrying ? 'animate-spin' : ''}`} />
          {isRetrying ? 'Connecting...' : 'Try Again Now'}
        </Button>

        <p className="text-xs text-muted-foreground">
          Auto-retrying in the background. You don't need to log in again.
        </p>
      </div>
    </PageTransition>
  )
}
