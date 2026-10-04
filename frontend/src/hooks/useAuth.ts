import { useAuthStore, selectUser, selectToken, selectAuthStatus, selectIsAuthenticated } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { authService } from '@/services/auth/authService'
import type { LoginFormData, RegisterFormData } from '@/utils/validators'

export function useAuth() {
  const status = useAuthStore(selectAuthStatus)
  const user = useAuthStore(selectUser)
  const token = useAuthStore(selectToken)
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  const login = async (data: LoginFormData) => {
    const tokenStr = await authService.login(data)

    // Temporarily set token in store so the apiClient interceptor uses it
    useAuthStore.setState({ token: tokenStr })

    try {
      // The profile will be fetched manually using the token via interceptor
      const profile = await authService.fetchBackendProfile()

      // WS-A7: Resolve workspace context authoritatively
      if (profile.tenant_id) {
        await useWorkspaceStore.getState().fetchCurrentWorkspace()
      } else {
        useWorkspaceStore.getState().resetWorkspaceResolution()
      }

      useAuthStore.getState().setAuth(profile, tokenStr)
    } catch (error) {
      useAuthStore.getState().clearAuth()
      useWorkspaceStore.getState().resetWorkspaceResolution()
      throw error
    }
  }

  const register = async (data: RegisterFormData) => {
    await authService.register(data)
  }

  const logout = async () => {
    await authService.logout()
    useAuthStore.getState().clearAuth()
    useWorkspaceStore.getState().resetWorkspaceResolution()
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
