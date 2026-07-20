import { useAuthStore, selectUser, selectToken, selectAuthStatus, selectIsAuthenticated } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'
import type { LoginFormData, RegisterFormData } from '@/utils/validators'

export function useAuth() {
  const status = useAuthStore(selectAuthStatus)
  const user = useAuthStore(selectUser)
  const token = useAuthStore(selectToken)
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  const login = async (data: LoginFormData) => {
    await authService.login(data)
  }

  const register = async (data: RegisterFormData) => {
    await authService.register(data)
  }

  const logout = async () => {
    await authService.logout()
    // State is cleared automatically via AuthProvider listening to Supabase onAuthStateChange
  }

  return {
    status,
    user,
    token,
    isAuthenticated,
    isLoading: status === 'LOADING',
    login,
    register,
    logout,
  }
}
