/**
 * Auth type definitions — mirror backend UserContext exactly.
 */

export type Role = 'admin' | 'user'

export type AuthStatus = 'UNAUTHENTICATED' | 'LOADING' | 'AUTHENTICATED' | 'ERROR'

export interface UserContext {
  id: string
  supabase_id: string
  email: string
  role: Role
  tenant_id: string | null
  workspace_name: string | null
  full_name: string | null
  is_active: boolean
  avatar_url?: string | null
  profile_data?: Record<string, any>
  preferences?: Record<string, any>
  workspace_settings?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface TokenPayload {
  sub: string
  email: string
  role?: Role
  aud?: string
  exp: number
  iat: number
}

export interface AuthState {
  status: AuthStatus
  user: UserContext | null
  token: string | null
}
