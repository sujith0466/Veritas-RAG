import { apiClient } from '@/api/client'

import { get, post } from '@/api/wrapper'
import type { UserContext } from '@/types'
import type { LoginFormData, RegisterFormData } from '@/utils/validators'

export const authService = {
  async login(data: LoginFormData) {
    const response = await post<{ access_token: string }>('/auth/login', {
      email: data.email,
      password: data.password,
    })
    
    // Memory storage of token and state will be handled by the authStore,
    // which intercepts this, or we could set it explicitly.
    // For F2.3 we just return the token if needed, or rely on authStore doing it.
    // Actually, `useAuthStore` uses `setToken`. Let's return the token so useAuth can store it.
    return response.access_token
  },

  async register(data: RegisterFormData) {
    // Send registration payload directly to our backend API
    await post('/auth/register', {
      email: data.email,
      password: data.password,
      full_name: data.fullName,
    })
  },

  async verifyEmail(email: string, token: string) {
    await get('/auth/verify', { email, token })
  },

  async resendVerification(email: string) {
    await post('/auth/resend-verification', { email })
  },

  async forgotPassword(email: string) {
    await post('/auth/forgot-password', { email })
  },

  async resetPassword(token: string, newPassword: string) {
    await post('/auth/reset-password', { token, new_password: newPassword })
  },

  async requestOTP(email: string) {
    await post('/auth/password/otp/request', { email })
  },

  async verifyOTP(email: string, otp: string) {
    await post('/auth/password/otp/verify', { email, otp })
  },

  async resetPasswordOTP(email: string, otp: string, newPassword: string) {
    await post('/auth/password/otp/reset', { email, otp, new_password: newPassword })
  },

  async changePassword(currentPassword: string, newPassword: string) {
    await post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },

  async logout() {
    try {
      await post('/auth/logout')
    } catch (error) {
      console.warn("Logout endpoint failed, proceeding with local logout", error)
    }
    
    // Broadcast channel logout (F2.4)
    const channel = new BroadcastChannel('auth_sync')
    channel.postMessage({ type: 'LOGOUT' })
    channel.close()
  },

  async refresh() {
    // The refresh_token is sent automatically via httpOnly cookies
    const response = await post<{ access_token: string }>('/auth/refresh')
    return response.access_token
  },

  async fetchBackendProfile(): Promise<UserContext> {
    let authContext: UserContext | null = null
    for (let i = 0; i < 3; i++) {
      try {
        authContext = await get<UserContext>('/auth/me')
        break
      } catch (error) {
        if (i === 2) throw error
        await new Promise(resolve => setTimeout(resolve, 1000))
      }
    }

    if (!authContext) throw new Error('Failed to fetch user context')

    try {
      const response = await apiClient.get('/users/me')
      return { ...authContext, ...response.data }
    } catch (error) {
      console.error('Failed to fetch extended user profile:', error)
      return authContext
    }
  },
}
