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

  // Auto-retry polling with backoff (capped at 15s)
  useEffect(() => {
    const interval = setInterval(() => {
      handleRetry()
    }, 5000)
    return () => clearInterval(interval)
  }, [token])

  const handleRetry = async () => {
    if (isRetrying) return
    setIsRetrying(true)
    setErrorMsg(null)

    try {
      let activeToken = token
      if (!activeToken) {
        // Cold-boot session restore: refresh access token first
        activeToken = await authService.refresh()
        useAuthStore.setState({ token: activeToken })
      }

      // Synchronize backend profile
      const userContext = await authService.fetchBackendProfile()
      setAuth(userContext, activeToken)
    } catch (err: any) {
      if (err?.status === 401) {
        // Server definitively rejected token (revoked or expired)
        useAuthStore.getState().clearAuth()
        return
      }
      setErrorMsg('Still unable to connect to the server. Will keep trying in the background.')
    } finally {
      setIsRetrying(false)
    }
  }

  const handleManualLogin = () => {
    useAuthStore.getState().clearAuth()
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

        <div className="flex flex-col sm:flex-row items-center gap-3 mt-6">
          <Button
            variant="default"
            size="lg"
            onClick={handleRetry}
            isLoading={isRetrying}
          >
            <RefreshCw className={`h-5 w-5 mr-2 ${isRetrying ? 'animate-spin' : ''}`} />
            {isRetrying ? 'Connecting...' : 'Try Again Now'}
          </Button>

          <Button
            variant="outline"
            size="lg"
            onClick={handleManualLogin}
          >
            Sign in with Password
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Auto-retrying in the background. You don't need to log in again if your session is active.
        </p>
      </div>
    </PageTransition>
  )
}
