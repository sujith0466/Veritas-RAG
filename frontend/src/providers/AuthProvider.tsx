import { useEffect, useRef } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { authService } from '@/services/auth/authService'

import { ApiError } from '@/types'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setStatus, setAuth, clearAuth, setErrorAuth, token, status } = useAuthStore()
  const initialMount = useRef(true)
  const isMountedRef = useRef(true)
  const authSeqRef = useRef(0)
  const initializedTokenRef = useRef<string | null | undefined>(undefined)
  const isInitializingRef = useRef(false)

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  useEffect(() => {
    async function initializeAuth() {
      // Do not race against OAuthCallbackPage when processing OAuth redirect
      if (typeof window !== 'undefined' && window.location.pathname.startsWith('/auth/callback')) {
        return
      }

      // If already unauthenticated and token is null, do not re-run refresh (prevents post-logout re-trigger)
      if (!token && status === 'UNAUTHENTICATED' && !initialMount.current) {
        initializedTokenRef.current = null
        return
      }

      // If this exact token is already in-flight or fully established, skip duplicate execution
      if (token && token === initializedTokenRef.current && (isInitializingRef.current || status === 'AUTHENTICATED')) {
        return
      }

      const seq = ++authSeqRef.current
      isInitializingRef.current = true

      try {
        if (initialMount.current) {
          setStatus('LOADING')
          initialMount.current = false
        }

        let currentToken = token

        if (!currentToken) {
          try {
            currentToken = await authService.refresh()
            if (!isMountedRef.current || seq !== authSeqRef.current) return

            // Record this token as recognized BEFORE updating Zustand store
            // to prevent the subsequent re-render from launching a duplicate initializeAuth run
            initializedTokenRef.current = currentToken
            useAuthStore.setState({ token: currentToken })
          } catch (e: any) {
            if (!isMountedRef.current || seq !== authSeqRef.current) return

            // Server authoritatively rejected session (cookie missing, expired, revoked)
            if (e instanceof ApiError && e.status === 401) {
              initializedTokenRef.current = null
              clearAuth()
              return
            }

            // Server is offline, starting up (502/503), timeout, or network disconnect
            // Retain recoverability: enter BACKEND_UNAVAILABLE rather than clearing credentials!
            useWorkspaceStore.getState().resetWorkspaceResolution()
            setErrorAuth('', {
              code: 'BACKEND_UNAVAILABLE',
              message: e instanceof ApiError && e.isGatewayError()
                ? 'Backend services are currently initializing. Reconnecting...'
                : 'Unable to connect to the server. Checking connection...',
              retryable: true,
              timestamp: Date.now(),
            })
            return
          }
        } else {
          initializedTokenRef.current = currentToken
        }

        if (!isMountedRef.current || seq !== authSeqRef.current) return

        // We have a token in memory, sync with backend
        const userContext = await authService.fetchBackendProfile()
        if (!isMountedRef.current || seq !== authSeqRef.current) return

        // WS-A7: Server-authoritative workspace context resolution
        if (userContext.tenant_id) {
          await useWorkspaceStore.getState().fetchCurrentWorkspace()
        } else {
          useWorkspaceStore.getState().resetWorkspaceResolution()
        }
        if (!isMountedRef.current || seq !== authSeqRef.current) return

        if (currentToken) {
          setAuth(userContext, currentToken)
        }
      } catch (error) {
        if (isMountedRef.current && seq === authSeqRef.current) {
          useWorkspaceStore.getState().resetWorkspaceResolution()
          if (token || initializedTokenRef.current) {
            setErrorAuth(token || (initializedTokenRef.current as string), {
              code: 'BACKEND_UNAVAILABLE',
              message: 'Failed to synchronize profile with backend.',
              retryable: true,
              timestamp: Date.now()
            })
          } else {
            clearAuth()
          }
        }
      } finally {
        if (seq === authSeqRef.current) {
          isInitializingRef.current = false
        }
      }
    }

    initializeAuth()
  }, [clearAuth, setAuth, setStatus, token, status])

  // F2.4: Listen to BroadcastChannel for cross-tab logout and demo role synchronization
  useEffect(() => {
    const channel = new BroadcastChannel('auth_sync')
    channel.onmessage = async (event) => {
      if (event.data?.type === 'LOGOUT') {
        if (isMountedRef.current) {
          authSeqRef.current++
          initializedTokenRef.current = null
          clearAuth()
          useWorkspaceStore.getState().resetWorkspaceResolution()
        }
      } else if (event.data?.type === 'TOKEN_REFRESHED' && event.data?.token) {
        if (isMountedRef.current) {
          try {
            const seq = ++authSeqRef.current
            initializedTokenRef.current = event.data.token
            useAuthStore.setState({ token: event.data.token })
            const userContext = await authService.fetchBackendProfile()
            if (!isMountedRef.current || seq !== authSeqRef.current) return
            if (userContext.tenant_id) {
              await useWorkspaceStore.getState().fetchCurrentWorkspace()
            } else {
              useWorkspaceStore.getState().resetWorkspaceResolution()
            }
            if (!isMountedRef.current || seq !== authSeqRef.current) return
            setAuth(userContext, event.data.token)
          } catch (e) {
            console.warn('Cross-tab token refresh sync failed:', e)
          }
        }
      } else if (event.data?.type === 'DEMO_ROLE_SWITCHED' || event.data?.type === 'DEMO_ROLE_RESET') {
        if (isMountedRef.current) {
          try {
            const seq = ++authSeqRef.current
            const refreshedToken = await authService.refresh()
            if (!isMountedRef.current || seq !== authSeqRef.current) return
            initializedTokenRef.current = refreshedToken
            useAuthStore.setState({ token: refreshedToken })
            const userContext = await authService.fetchBackendProfile()
            if (!isMountedRef.current || seq !== authSeqRef.current) return
            if (userContext.tenant_id) {
              await useWorkspaceStore.getState().fetchCurrentWorkspace()
            } else {
              useWorkspaceStore.getState().resetWorkspaceResolution()
            }
            if (!isMountedRef.current || seq !== authSeqRef.current) return
            setAuth(userContext, refreshedToken)
          } catch (e) {
            console.warn('Cross-tab demo sync failed:', e)
          }
        }
      }
    }

    return () => {
      channel.close()
    }
  }, [clearAuth, setAuth])

  return (
    <AuthContext.Provider value={null}>
      {children}
    </AuthContext.Provider>
  )
}
