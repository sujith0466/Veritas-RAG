/**
 * Auth type definitions — mirror backend UserContext exactly.
 */

export type Role = 'admin' | 'engineer' | 'analyst' | 'viewer'

export type AuthStatus = 'UNAUTHENTICATED' | 'LOADING' | 'AUTHENTICATED' | 'ERROR'

export interface UserContext {
  id: string
  supabase_id: string
  email: string
  role: Role
  tenant_id: string | null
  full_name: string | null
  is_active: boolean
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
