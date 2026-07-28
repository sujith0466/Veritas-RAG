import { useEffect, useRef } from 'react'
import { AuthContext } from '@/contexts/AuthContext'
import { useAuthStore } from '@/stores/authStore'
import { supabaseClient } from '@/services/auth/supabaseClient'
import { authService } from '@/services/auth/authService'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setStatus, setAuth, clearAuth } = useAuthStore()
  const initialMount = useRef(true)

  useEffect(() => {
    let mounted = true

    async function initializeAuth() {
      try {
        if (initialMount.current) {
          setStatus('LOADING')
          initialMount.current = false
        }

        const { data: { session }, error } = await supabaseClient.auth.getSession()

        if (error || !session) {
          if (mounted) clearAuth()
          return
        }

        // We have a Supabase session, now strictly sync with backend
        const userContext = await authService.fetchBackendProfile()
        
        if (mounted) {
          setAuth(userContext, session.access_token)
        }
      } catch (error) {
        if (mounted) {
          clearAuth()
        }
      }
    }

    initializeAuth()

    const { data: { subscription } } = supabaseClient.auth.onAuthStateChange(
      async (event, session) => {
        if (!mounted) return

        if (event === 'SIGNED_OUT' || !session) {
          clearAuth()
          return
        }

        if (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') {
          // If we already have the user and it's just a token refresh, skip backend profile fetch
          const currentUser = useAuthStore.getState().user
          if (currentUser && event === 'TOKEN_REFRESHED') {
            setAuth(currentUser, session.access_token)
            return
          }

          try {
            const userContext = await authService.fetchBackendProfile()
            setAuth(userContext, session.access_token)
          } catch {
            clearAuth()
          }
        }
      }
    )

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [clearAuth, setAuth, setStatus])

  return (
    <AuthContext.Provider value={null}>
      {children}
    </AuthContext.Provider>
  )
}
