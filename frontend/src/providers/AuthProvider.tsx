import { useEffect, useRef } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setStatus, setAuth, clearAuth, setErrorAuth, token } = useAuthStore()
  const initialMount = useRef(true)

  useEffect(() => {
    let mounted = true

    async function initializeAuth() {
      try {
        if (initialMount.current) {
          setStatus('LOADING')
          initialMount.current = false
        }

        if (!token) {
          if (mounted) clearAuth()
          return
        }

        // We have a token in memory, sync with backend
        const userContext = await authService.fetchBackendProfile()

        if (mounted) {
          setAuth(userContext, token)
        }
      } catch (error) {
        if (mounted) {
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

    // F2.4: Listen to BroadcastChannel for cross-tab logout synchronization
    const channel = new BroadcastChannel('auth_sync')
    channel.onmessage = (event) => {
      if (event.data?.type === 'LOGOUT') {
        if (mounted) clearAuth()
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
