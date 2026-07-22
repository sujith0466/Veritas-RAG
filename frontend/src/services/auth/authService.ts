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
    // If role is user, tenant_id is the invitation code. 
    // If role is admin, the tenant_id will be set to their own supabase_id during backend sync or they own the workspace.
    // However, the backend sync handles 'tenant_id' and 'workspace_name' from claims.
    const metadata: Record<string, any> = {
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
