import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { AuthProvider } from '@/providers/AuthProvider'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { authService } from '@/services/auth/authService'
import { ApiError } from '@/types'

vi.mock('@/services/auth/authService', () => ({
  authService: {
    refresh: vi.fn(),
    fetchBackendProfile: vi.fn(),
    logout: vi.fn(),
  },
}))

describe('AuthProvider Session Restoration & Lifecycle', () => {
  const mockUserContext = {
    id: 'user-123',
    email: 'admin@veritasrag.com',
    role: 'admin',
    tenant_id: 'tenant-456',
    full_name: 'Veritas Admin',
  }

  const mockWorkspace = {
    id: 'tenant-456',
    name: 'Primary Enterprise Workspace',
    slug: 'primary-enterprise',
    status: 'ACTIVE' as const,
    provisioning_status: 'READY' as const,
    updated_at: new Date().toISOString(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      status: 'LOADING',
      user: null,
      token: null,
      error: undefined,
    })
    useWorkspaceStore.setState({
      currentWorkspace: null,
      isResolvingWorkspace: false,
    })

    vi.spyOn(useWorkspaceStore.getState(), 'fetchCurrentWorkspace').mockImplementation(async () => {
      useWorkspaceStore.setState({ currentWorkspace: mockWorkspace, isResolvingWorkspace: false })
      return mockWorkspace
    })

    vi.mocked(authService.refresh).mockResolvedValue('jwt-mock-access-token-xyz')
    vi.mocked(authService.fetchBackendProfile).mockResolvedValue(mockUserContext as any)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('restores valid session on cold start with EXACTLY ONE call to refresh, fetchBackendProfile, and fetchCurrentWorkspace (no duplicate cascade)', async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <div>Child Content</div>
        </AuthProvider>
      )
      // Allow async chain to settle
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(authService.refresh).toHaveBeenCalledTimes(1)
    expect(authService.fetchBackendProfile).toHaveBeenCalledTimes(1)
    expect(useWorkspaceStore.getState().fetchCurrentWorkspace).toHaveBeenCalledTimes(1)

    const state = useAuthStore.getState()
    expect(state.status).toBe('AUTHENTICATED')
    expect(state.token).toBe('jwt-mock-access-token-xyz')
    expect(state.user).toEqual(mockUserContext)
    expect(useWorkspaceStore.getState().currentWorkspace).toEqual(mockWorkspace)
  })

  it('handles 401 on refresh by authoritatively transitioning to UNAUTHENTICATED without fetching profile', async () => {
    const unauthorizedError = new ApiError('Session expired', 'UNAUTHORIZED', 401, 'req-001')
    vi.mocked(authService.refresh).mockRejectedValue(unauthorizedError)

    await act(async () => {
      render(
        <AuthProvider>
          <div>Child Content</div>
        </AuthProvider>
      )
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(authService.refresh).toHaveBeenCalledTimes(1)
    expect(authService.fetchBackendProfile).not.toHaveBeenCalled()
    expect(useWorkspaceStore.getState().fetchCurrentWorkspace).not.toHaveBeenCalled()

    const state = useAuthStore.getState()
    expect(state.status).toBe('UNAUTHENTICATED')
    expect(state.token).toBeNull()
    expect(state.user).toBeNull()
  })

  it('handles backend offline (502/503/timeout) by setting BACKEND_UNAVAILABLE with retryable error', async () => {
    const gatewayError = new ApiError('Bad Gateway', 'GATEWAY_ERROR', 502, 'req-502')
    vi.mocked(authService.refresh).mockRejectedValue(gatewayError)

    await act(async () => {
      render(
        <AuthProvider>
          <div>Child Content</div>
        </AuthProvider>
      )
      await Promise.resolve()
      await Promise.resolve()
    })

    const state = useAuthStore.getState()
    expect(state.status).toBe('ERROR')
    expect(state.error?.code).toBe('BACKEND_UNAVAILABLE')
    expect(state.error?.retryable).toBe(true)
    expect(authService.fetchBackendProfile).not.toHaveBeenCalled()
  })

  it('handles legitimate external token change by synchronizing new profile without duplication', async () => {
    // 1. First establish initial session
    await act(async () => {
      render(
        <AuthProvider>
          <div>Child Content</div>
        </AuthProvider>
      )
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(authService.fetchBackendProfile).toHaveBeenCalledTimes(1)

    // 2. Now simulate a legitimate token change (e.g. demo role switch or workspace switch)
    const newContext = { ...mockUserContext, role: 'owner' }
    vi.mocked(authService.fetchBackendProfile).mockResolvedValueOnce(newContext as any)

    await act(async () => {
      useAuthStore.setState({ token: 'new-rotated-token-999' })
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(authService.fetchBackendProfile).toHaveBeenCalledTimes(2)
    expect(useAuthStore.getState().user?.role).toBe('owner')
    expect(useAuthStore.getState().token).toBe('new-rotated-token-999')
  })

  it('does NOT re-trigger refresh or fetch profile after logout sets token to null and status to UNAUTHENTICATED', async () => {
    await act(async () => {
      render(
        <AuthProvider>
          <div>Child Content</div>
        </AuthProvider>
      )
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(authService.refresh).toHaveBeenCalledTimes(1)
    expect(authService.fetchBackendProfile).toHaveBeenCalledTimes(1)

    // Simulate logout
    await act(async () => {
      useAuthStore.getState().clearAuth()
      await Promise.resolve()
      await Promise.resolve()
    })

    // Refresh and fetchBackendProfile must NOT be called again
    expect(authService.refresh).toHaveBeenCalledTimes(1)
    expect(authService.fetchBackendProfile).toHaveBeenCalledTimes(1)
    expect(useAuthStore.getState().status).toBe('UNAUTHENTICATED')
  })
})
