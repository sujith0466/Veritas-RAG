import * as React from 'react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Shield, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/common/Button'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'

export function OAuthCallbackPage(): React.JSX.Element {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const isProcessing = useRef(false)

  const processCallback = React.useCallback(async () => {
    // Check if error parameter is present in URL search params (e.g., ?error=sso_failed)
    const errorParam = searchParams.get('error')
    if (errorParam) {
      setStatus('error')
      if (errorParam === 'access_denied') {
        setErrorMessage('Google Sign-In was cancelled. Please try again.')
      } else if (errorParam === 'account_disabled') {
        setErrorMessage('Your account is currently disabled. Please contact support.')
      } else {
        setErrorMessage('Google authentication failed. Please check your credentials and try again.')
      }
      return
    }

    // Extract access_token from URL fragment (#access_token=...)
    const hash = window.location.hash
    let accessToken: string | null = null

    if (hash && hash.includes('access_token=')) {
      const match = hash.match(/access_token=([^&]+)/)
      if (match && match[1]) {
        accessToken = decodeURIComponent(match[1])
      }
    }

    // Immediately sanitize URL bar to prevent token leakage in browser history/screen capture
    if (window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
    }

    if (!accessToken) {
      // If no token in hash, attempt cookie refresh as a fallback
      try {
        accessToken = await authService.refresh()
      } catch {
        setStatus('error')
        setErrorMessage('No authentication token received from identity provider.')
        return
      }
    }

    try {
      // Store token in memory only (Zustand) for apiClient Authorization header
      useAuthStore.setState({ token: accessToken })

      // Fetch user profile and workspace context from backend
      const userContext = await authService.fetchBackendProfile()

      // Establish authenticated status
      useAuthStore.getState().setAuth(userContext, accessToken)

      setStatus('success')

      // Purge client join_intent cache now that backend has processed it
      try {
        sessionStorage.removeItem('join_intent')
      } catch {
        // Ignore sessionStorage errors
      }

      // Short visual confirmation before routing to workspace or onboarding
      setTimeout(() => {
        if (!userContext.workspace_id) {
          navigate('/onboarding', { replace: true })
        } else {
          navigate('/dashboard', { replace: true })
        }
      }, 500)
    } catch (err) {
      useAuthStore.getState().clearAuth()
      setStatus('error')
      setErrorMessage(
        err instanceof Error ? err.message : 'Failed to synchronize workspace profile. Please try again.'
      )
    }
  }, [navigate, searchParams])

  useEffect(() => {
    // Prevent double-execution in React 18 StrictMode mount/unmount cycle
    if (isProcessing.current) return
    isProcessing.current = true

    processCallback()
  }, [processCallback])

  if (status === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center space-y-5 animate-in fade-in duration-300">
        <div className="relative flex items-center justify-center">
          <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center border border-primary/20 animate-pulse">
            <Shield className="h-8 w-8 text-primary animate-bounce-subtle" />
          </div>
        </div>
        <div className="space-y-1.5">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">
            Authenticating with Google
          </h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            Verifying your identity and establishing a secure workspace session...
          </p>
        </div>
        <div className="w-48 h-1 bg-surface-elevated rounded-full overflow-hidden">
          <div className="h-full bg-primary animate-progress rounded-full" />
        </div>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center space-y-4 animate-in fade-in duration-200">
        <div className="h-16 w-16 rounded-2xl bg-success/10 flex items-center justify-center border border-success/20">
          <CheckCircle2 className="h-8 w-8 text-success" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">
            Authentication Verified
          </h2>
          <p className="text-sm text-muted-foreground">
            Redirecting to your workspace...
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center space-y-5 animate-in fade-in duration-200">
      <div className="h-16 w-16 rounded-2xl bg-danger/10 flex items-center justify-center border border-danger/20">
        <AlertCircle className="h-8 w-8 text-danger" />
      </div>
      <div className="space-y-1.5">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Sign-In Failed
        </h2>
        <p className="text-sm text-muted-foreground max-w-md">
          {errorMessage || 'An unexpected error occurred during Google authentication.'}
        </p>
      </div>
      <div className="flex items-center gap-3 pt-2">
        <Button
          variant="outline"
          onClick={() => {
            isProcessing.current = false
            setStatus('loading')
            setErrorMessage(null)
            processCallback()
          }}
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Try Again
        </Button>
        <Button
          variant="default"
          onClick={() => navigate('/auth/login', { replace: true })}
        >
          Return to Login
        </Button>
      </div>
    </div>
  )
}
