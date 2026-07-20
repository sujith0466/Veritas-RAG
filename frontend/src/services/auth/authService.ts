import { supabaseClient } from './supabaseClient'
import { get } from '@/api/wrapper'
import type { UserContext } from '@/types'
import type { LoginFormData, RegisterFormData } from '@/utils/validators'

export const authService = {
  async login(data: LoginFormData) {
    const { error } = await supabaseClient.auth.signInWithPassword({
      email: data.email,
      password: data.password,
    })
    if (error) throw new Error(error.message)
  },

  async register(data: RegisterFormData) {
    const { error } = await supabaseClient.auth.signUp({
      email: data.email,
      password: data.password,
      options: {
        data: {
          full_name: data.fullName,
        },
      },
    })
    if (error) throw new Error(error.message)
  },

  async logout() {
    const { error } = await supabaseClient.auth.signOut()
    if (error) throw new Error(error.message)
  },

  async fetchBackendProfile(): Promise<UserContext> {
    return await get<UserContext>('/auth/me')
  },
}
