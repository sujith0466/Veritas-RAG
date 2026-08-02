import { useAuthStore, selectUser, selectToken, selectAuthStatus, selectIsAuthenticated } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'
import type { LoginFormData, RegisterFormData } from '@/utils/validators'

export function useAuth() {
  const status = useAuthStore(selectAuthStatus)
  const user = useAuthStore(selectUser)
  const token = useAuthStore(selectToken)
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  const login = async (data: LoginFormData) => {
    const tokenStr = await authService.login(data)
    // The profile will be fetched manually
    const profile = await authService.fetchBackendProfile()
    useAuthStore.getState().setAuth(profile, tokenStr)
  }

  const register = async (data: RegisterFormData) => {
    await authService.register(data)
  }

  const logout = async () => {
    await authService.logout()
    useAuthStore.getState().clearAuth()
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
