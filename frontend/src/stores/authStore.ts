import { create } from 'zustand'
import type { AuthStatus, UserContext, AuthError } from '@/types'
import { storage, STORAGE_KEYS } from '@/utils/storage'

interface AuthStoreState {
  status: AuthStatus
  user: UserContext | null
  token: string | null
  error?: AuthError
}

interface AuthStoreActions {
  setStatus: (status: AuthStatus) => void
  setAuth: (user: UserContext, token: string) => void
  setToken: (token: string) => void
  clearAuth: () => void
  setErrorAuth: (token: string, error: AuthError) => void
  updateUser: (user: Partial<UserContext>) => void
}

const initialState: AuthStoreState = {
  status: 'LOADING',
  user: null,
  token: null,
}

export const useAuthStore = create<AuthStoreState & AuthStoreActions>()((set) => ({
  ...initialState,

  setStatus: (status) => set({ status }),

  setAuth: (user, token) => {
    storage.set(STORAGE_KEYS.SESSION_HINT, true)
    return set({ status: 'AUTHENTICATED', user, token, error: undefined })
  },

  setToken: (token) =>
    set({ token, status: 'AUTHENTICATED', error: undefined }),

  clearAuth: () => {
    storage.remove(STORAGE_KEYS.SESSION_HINT)
    return set({ ...initialState, status: 'UNAUTHENTICATED' })
  },

  setErrorAuth: (token, error) =>
    set({ status: 'ERROR', user: null, token, error }),

  updateUser: (partialUser) =>
    set((state) => ({
      user: state.user ? { ...state.user, ...partialUser } : null,
    })),
}))

// ─── Typed selectors ──────────────────────────────────────────────────────────
export const selectAuthStatus = (s: AuthStoreState & AuthStoreActions) => s.status
export const selectUser = (s: AuthStoreState & AuthStoreActions) => s.user
export const selectToken = (s: AuthStoreState & AuthStoreActions) => s.token
export const selectIsAuthenticated = (s: AuthStoreState & AuthStoreActions) =>
  s.status === 'AUTHENTICATED'
