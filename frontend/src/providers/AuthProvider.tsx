import { useEffect, useRef } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { authService } from '@/services/auth/authService'

import { ApiError } from '@/types'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setStatus, setAuth, clearAuth, setErrorAuth, token } = useAuthStore()
  const initialMount = useRef(true)

  useEffect(() => {
    let mounted = true

    async function initializeAuth() {
      // Do not race against OAuthCallbackPage when processing OAuth redirect
      if (window.location.pathname.startsWith('/auth/callback')) {
        return
      }

      try {
        if (initialMount.current) {
          setStatus('LOADING')
          initialMount.current = false
        }

        let currentToken = token

        if (!currentToken) {
          try {
            currentToken = await authService.refresh()
            // Temporarily store token for apiClient interceptor
            useAuthStore.setState({ token: currentToken })
          } catch (e: any) {
            if (!mounted) return

            // Server authoritatively rejected session (cookie missing, expired, revoked)
            if (e instanceof ApiError && e.status === 401) {
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
        }

        // We have a token in memory, sync with backend
        const userContext = await authService.fetchBackendProfile()

        // WS-A7: Server-authoritative workspace context resolution
        if (userContext.tenant_id) {
          await useWorkspaceStore.getState().fetchCurrentWorkspace()
        } else {
          useWorkspaceStore.getState().resetWorkspaceResolution()
        }

        if (mounted && currentToken) {
          setAuth(userContext, currentToken)
        }
      } catch (error) {
        if (mounted) {
          useWorkspaceStore.getState().resetWorkspaceResolution()
          if (token) {
            setErrorAuth(token, {
              code: 'BACKEND_UNAVAILABLE',
              message: 'Failed to synchronize profile with backend.',
              retryable: true,
              timestamp: Date.now()
            })
          } else {
            clearAuth()
          }
        }
      }
    }

    initializeAuth()

    // F2.4: Listen to BroadcastChannel for cross-tab logout and demo role synchronization
    const channel = new BroadcastChannel('auth_sync')
    channel.onmessage = async (event) => {
      if (event.data?.type === 'LOGOUT') {
        if (mounted) {
          clearAuth()
          useWorkspaceStore.getState().resetWorkspaceResolution()
        }
      } else if (event.data?.type === 'TOKEN_REFRESHED' && event.data?.token) {
        if (mounted) {
          try {
            // Adopt token refreshed by another tab and sync profile
            useAuthStore.setState({ token: event.data.token })
            const userContext = await authService.fetchBackendProfile()
            if (userContext.tenant_id) {
              await useWorkspaceStore.getState().fetchCurrentWorkspace()
            } else {
              useWorkspaceStore.getState().resetWorkspaceResolution()
            }
            if (mounted) {
              setAuth(userContext, event.data.token)
            }
          } catch (e) {
            console.warn('Cross-tab token refresh sync failed:', e)
          }
        }
      } else if (event.data?.type === 'DEMO_ROLE_SWITCHED' || event.data?.type === 'DEMO_ROLE_RESET') {
        if (mounted) {
          try {
            // Silently refresh token and update profile across open tabs
            const refreshedToken = await authService.refresh()
            useAuthStore.setState({ token: refreshedToken })
            const userContext = await authService.fetchBackendProfile()
            if (userContext.tenant_id) {
              await useWorkspaceStore.getState().fetchCurrentWorkspace()
            } else {
              useWorkspaceStore.getState().resetWorkspaceResolution()
            }
            if (mounted) {
              setAuth(userContext, refreshedToken)
            }
          } catch (e) {
            console.warn('Cross-tab demo sync failed:', e)
          }
        }
      }
    }

    return () => {
      mounted = false
      channel.close()
    }
  }, [clearAuth, setAuth, setStatus, token])

  return (
    <AuthContext.Provider value={null}>
      {children}
    </AuthContext.Provider>
  )
}
