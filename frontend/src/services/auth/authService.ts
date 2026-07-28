import { apiClient } from '@/api/client'
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
    if (error) throw new Error((error as Error).message)
  },

  async register(data: RegisterFormData) {
    // If role is user, tenant_id is the invitation code. 
    // If role is admin, the tenant_id will be set to their own supabase_id during backend sync or they own the workspace.
    // However, the backend sync handles 'tenant_id' and 'workspace_name' from claims.
    const metadata: Record<string, unknown> = {
      full_name: data.fullName,
      role: data.role || 'user',
    }

    if (data.role === 'admin') {
      metadata.workspace_name = data.workspaceName
      metadata.organization_name = data.organizationName
    } else if (data.role === 'user') {
      metadata.tenant_id = data.invitationCode
    }

    const { error } = await supabaseClient.auth.signUp({
      email: data.email,
      password: data.password,
      options: {
        data: metadata,
      },
    })
    if (error) throw new Error((error as Error).message)
  },

  async logout() {
    const { error } = await supabaseClient.auth.signOut()
    if (error) throw new Error((error as Error).message)
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
