import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { PostAuthenticationRouteResolver } from '@/components/auth/PostAuthenticationRouteResolver'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { dashboardService } from '@/services/dashboardService'
import { ApiError } from '@/types/api'

vi.mock('@/services/dashboardService', () => ({
  dashboardService: {
    getKnowledgeIntelligenceSummary: vi.fn(),
  },
}))

vi.mock('@/services/userService', () => ({
  userService: {
    updateWorkspace: vi.fn(),
  },
}))

describe('PostAuthenticationRouteResolver P0-3 Gateway Resilience', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(dashboardService.getKnowledgeIntelligenceSummary).mockResolvedValue({
      total_documents: 0,
      total_chunks: 0,
      vector_count: 0,
      pipeline_status: 'IDLE',
      health_score: 100,
    } as any)
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      token: 'valid-jwt-token',
      user: {
        id: 'usr-1',
        email: 'test@example.com',
        role: 'member',
        tenant_id: 'ws-1',
        workspace_settings: { onboarding_completed: false },
      } as any,
      error: undefined,
    })
    useWorkspaceStore.setState({
      currentWorkspace: { id: 'ws-1', name: 'Test Workspace' } as any,
      isResolvingWorkspace: false,
    })
  })

  it('delegates HTTP 502 gateway error to useAuthStore.setErrorAuth with BACKEND_UNAVAILABLE', async () => {
    const gatewayError = new ApiError('Bad Gateway', 'GATEWAY_ERROR', 502, 'req-502')
    vi.mocked(dashboardService.getKnowledgeIntelligenceSummary).mockRejectedValue(gatewayError)

    const setErrorAuthSpy = vi.spyOn(useAuthStore.getState(), 'setErrorAuth')

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PostAuthenticationRouteResolver />}>
            <Route index element={<div data-testid="outlet-content">Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(setErrorAuthSpy).toHaveBeenCalledWith(
        'valid-jwt-token',
        expect.objectContaining({
          code: 'BACKEND_UNAVAILABLE',
          retryable: true,
        })
      )
    })
  })

  it('delegates HTTP 503 service unavailable error to useAuthStore.setErrorAuth with BACKEND_UNAVAILABLE', async () => {
    const gatewayError = new ApiError('Service Unavailable', 'SERVICE_UNAVAILABLE', 503, 'req-503')
    vi.mocked(dashboardService.getKnowledgeIntelligenceSummary).mockRejectedValue(gatewayError)

    const setErrorAuthSpy = vi.spyOn(useAuthStore.getState(), 'setErrorAuth')

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PostAuthenticationRouteResolver />}>
            <Route index element={<div data-testid="outlet-content">Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(setErrorAuthSpy).toHaveBeenCalledWith(
        'valid-jwt-token',
        expect.objectContaining({
          code: 'BACKEND_UNAVAILABLE',
          retryable: true,
        })
      )
    })
  })

  it('clears auth on HTTP 401 unauthorized error', async () => {
    const authError = new ApiError('Unauthorized', 'UNAUTHORIZED', 401, 'req-401')
    vi.mocked(dashboardService.getKnowledgeIntelligenceSummary).mockRejectedValue(authError)

    const clearAuthSpy = vi.spyOn(useAuthStore.getState(), 'clearAuth')

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PostAuthenticationRouteResolver />}>
            <Route index element={<div data-testid="outlet-content">Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(clearAuthSpy).toHaveBeenCalled()
    })
  })

  it('renders local retry prompt for generic non-gateway application errors (HTTP 500)', async () => {
    const appError = new ApiError('Internal Error', 'INTERNAL_ERROR', 500, 'req-500')
    vi.mocked(dashboardService.getKnowledgeIntelligenceSummary).mockRejectedValue(appError)

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PostAuthenticationRouteResolver />}>
            <Route index element={<div data-testid="outlet-content">Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByText('Workspace Resolution Failed')).toBeInTheDocument()
    expect(screen.getByText('Unable to fetch workspace status. Please check your connection.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('renders outlet immediately when onboarding_completed is already true', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-1',
        email: 'test@example.com',
        role: 'member',
        tenant_id: 'ws-1',
        workspace_settings: { onboarding_completed: true },
      } as any,
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<PostAuthenticationRouteResolver />}>
            <Route index element={<div data-testid="outlet-content">Protected Content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    )

    expect(await screen.findByTestId('outlet-content')).toBeInTheDocument()
    expect(dashboardService.getKnowledgeIntelligenceSummary).not.toHaveBeenCalled()
  })
})
