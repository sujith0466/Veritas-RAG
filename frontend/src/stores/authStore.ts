import { create } from 'zustand'
import type { AuthStatus, UserContext } from '@/types'

interface AuthStoreState {
  status: AuthStatus
  user: UserContext | null
  token: string | null
}

interface AuthStoreActions {
  setStatus: (status: AuthStatus) => void
  setAuth: (user: UserContext, token: string) => void
  clearAuth: () => void
}

const initialState: AuthStoreState = {
  status: 'UNAUTHENTICATED',
  user: null,
  token: null,
}

export const useAuthStore = create<AuthStoreState & AuthStoreActions>()((set) => ({
  ...initialState,

  setStatus: (status) => set({ status }),

  setAuth: (user, token) =>
    set({ status: 'AUTHENTICATED', user, token }),

  clearAuth: () =>
    set({ ...initialState, status: 'UNAUTHENTICATED' }),
}))

// ─── Typed selectors ──────────────────────────────────────────────────────────
export const selectAuthStatus = (s: AuthStoreState & AuthStoreActions) => s.status
export const selectUser = (s: AuthStoreState & AuthStoreActions) => s.user
export const selectToken = (s: AuthStoreState & AuthStoreActions) => s.token
export const selectIsAuthenticated = (s: AuthStoreState & AuthStoreActions) =>
  s.status === 'AUTHENTICATED'
