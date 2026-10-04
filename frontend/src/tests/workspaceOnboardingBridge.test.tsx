import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { ProtectedRoute, PublicOnlyRoute, OnboardingRoute } from '@/routes'
import { getSafeRedirectUrl } from '@/utils/redirect'
import { WorkspaceOnboardingPage } from '@/pages/onboarding/WorkspaceOnboardingPage'
import { workspaceService } from '@/services/workspaceService'

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getUserWorkspaces: vi.fn(),
    switchWorkspace: vi.fn(),
    getCurrentWorkspace: vi.fn(),
  },
}))

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    logout: vi.fn(),
  }),
}))

describe('WS-A7: Open Redirect Protection (getSafeRedirectUrl)', () => {
  it('falls back safely for absolute external URLs', () => {
    expect(getSafeRedirectUrl('https://evil.com')).toBe('/dashboard')
    expect(getSafeRedirectUrl('http://evil.com/phish')).toBe('/dashboard')
    expect(getSafeRedirectUrl('ftp://evil.com')).toBe('/dashboard')
  })

  it('falls back safely for protocol-relative and UNC bypasses', () => {
    expect(getSafeRedirectUrl('//evil.com')).toBe('/dashboard')
    expect(getSafeRedirectUrl('//evil.com/path')).toBe('/dashboard')
    expect(getSafeRedirectUrl('/\\evil.com')).toBe('/dashboard')
    expect(getSafeRedirectUrl('/\\evil.com/path')).toBe('/dashboard')
  })

  it('falls back safely for pseudo-protocols (javascript:, data:)', () => {
    expect(getSafeRedirectUrl('javascript:alert(1)')).toBe('/dashboard')
    expect(getSafeRedirectUrl('data:text/html;base64,...')).toBe('/dashboard')
    expect(getSafeRedirectUrl('blob:https://evil.com')).toBe('/dashboard')
  })

  it('falls back safely for auth loop paths', () => {
    expect(getSafeRedirectUrl('/auth/login')).toBe('/dashboard')
    expect(getSafeRedirectUrl('/auth/register')).toBe('/dashboard')
    expect(getSafeRedirectUrl('/auth/callback?code=123')).toBe('/dashboard')
  })

  it('preserves valid relative paths and queries', () => {
    expect(getSafeRedirectUrl('/dashboard')).toBe('/dashboard')
    expect(getSafeRedirectUrl('/chat')).toBe('/chat')
    expect(getSafeRedirectUrl('/settings/profile?tab=security')).toBe('/settings/profile?tab=security')
    expect(getSafeRedirectUrl('/workspaces/new')).toBe('/workspaces/new')
  })

  it('uses custom fallback when specified', () => {
    expect(getSafeRedirectUrl('https://evil.com', '/onboarding')).toBe('/onboarding')
    expect(getSafeRedirectUrl(null, '/onboarding')).toBe('/onboarding')
  })
})

describe('WS-A7: Route Guards & Onboarding Bridge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: null,
      status: 'UNAUTHENTICATED',
      error: undefined,
    })
    useWorkspaceStore.setState({
      currentWorkspace: null,
      isResolvingWorkspace: false,
      memberships: [],
      error: null,
    })
  })

  describe('ProtectedRoute', () => {
    it('1. Unauthenticated user hitting /dashboard redirects to /auth/login?redirect=%2Fdashboard', () => {
      render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div data-testid="dashboard">Dashboard Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/auth/login" element={<div data-testid="login">Login Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('login')).toBeInTheDocument()
      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
    })

    it('2. Unauthenticated user hitting /workspaces/new redirects to /auth/login?redirect=%2Fworkspaces%2Fnew', () => {
      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <Routes>
            <Route
              path="/workspaces/new"
              element={
                <ProtectedRoute requireWorkspace={false}>
                  <div data-testid="create-ws">Create WS Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/auth/login" element={<div data-testid="login">Login Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('login')).toBeInTheDocument()
      expect(screen.queryByTestId('create-ws')).not.toBeInTheDocument()
    })

    it('3. Authenticated user without workspace hitting /dashboard redirects to /onboarding', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div data-testid="dashboard">Dashboard Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('onboarding')).toBeInTheDocument()
      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
    })

    it('4. Authenticated user without workspace hitting /chat redirects to /onboarding', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/chat']}>
          <Routes>
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <div data-testid="chat">Chat Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('onboarding')).toBeInTheDocument()
      expect(screen.queryByTestId('chat')).not.toBeInTheDocument()
    })

    it('5. Authenticated user without workspace hitting /workspaces/new is allowed', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/workspaces/new']}>
          <Routes>
            <Route
              path="/workspaces/new"
              element={
                <ProtectedRoute requireWorkspace={false}>
                  <div data-testid="create-ws">Create WS Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('create-ws')).toBeInTheDocument()
      expect(screen.queryByTestId('onboarding')).not.toBeInTheDocument()
    })

    it('6. Authenticated user with active workspace is allowed on /dashboard', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: 'ws-123' } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: { id: 'ws-123', name: 'Acme Corp', slug: 'acme' } as any,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div data-testid="dashboard">Dashboard Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      expect(screen.queryByTestId('onboarding')).not.toBeInTheDocument()
    })

    it('7. Renders loading state while isResolvingWorkspace is true (no premature redirect)', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: true,
      })

      const { container } = render(
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <div data-testid="dashboard">Dashboard Content</div>
                </ProtectedRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
      expect(screen.queryByTestId('onboarding')).not.toBeInTheDocument()
      expect(container.querySelector('.animate-spin')).toBeInTheDocument()
    })
  })

  describe('OnboardingRoute', () => {
    it('8. Unauthenticated user hitting /onboarding redirects to /auth/login?redirect=/onboarding', () => {
      render(
        <MemoryRouter initialEntries={['/onboarding']}>
          <Routes>
            <Route
              path="/onboarding"
              element={
                <OnboardingRoute>
                  <div data-testid="onboarding-content">Onboarding Content</div>
                </OnboardingRoute>
              }
            />
            <Route path="/auth/login" element={<div data-testid="login">Login Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('login')).toBeInTheDocument()
      expect(screen.queryByTestId('onboarding-content')).not.toBeInTheDocument()
    })

    it('9. Authenticated user without workspace stays on /onboarding', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/onboarding']}>
          <Routes>
            <Route
              path="/onboarding"
              element={
                <OnboardingRoute>
                  <div data-testid="onboarding-content">Onboarding Content</div>
                </OnboardingRoute>
              }
            />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('onboarding-content')).toBeInTheDocument()
      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
    })

    it('10. Authenticated user with active workspace hitting /onboarding redirects to /dashboard', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: 'ws-123' } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: { id: 'ws-123', name: 'Acme Corp' } as any,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/onboarding']}>
          <Routes>
            <Route
              path="/onboarding"
              element={
                <OnboardingRoute>
                  <div data-testid="onboarding-content">Onboarding Content</div>
                </OnboardingRoute>
              }
            />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('dashboard')).toBeInTheDocument()
      expect(screen.queryByTestId('onboarding-content')).not.toBeInTheDocument()
    })
  })

  describe('PublicOnlyRoute', () => {
    it('11. Authenticated user without workspace is redirected to /onboarding', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: null } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: null,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/auth/login']}>
          <Routes>
            <Route
              path="/auth/login"
              element={
                <PublicOnlyRoute>
                  <div data-testid="login-content">Login Form</div>
                </PublicOnlyRoute>
              }
            />
            <Route path="/onboarding" element={<div data-testid="onboarding">Onboarding Bridge</div>} />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('onboarding')).toBeInTheDocument()
      expect(screen.queryByTestId('login-content')).not.toBeInTheDocument()
      expect(screen.queryByTestId('dashboard')).not.toBeInTheDocument()
    })

    it('12. Authenticated user with active workspace is redirected to /dashboard or safe redirect', () => {
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'user@test.com', role: 'member', tenant_id: 'ws-1' } as any,
      })
      useWorkspaceStore.setState({
        currentWorkspace: { id: 'ws-1' } as any,
        isResolvingWorkspace: false,
      })

      render(
        <MemoryRouter initialEntries={['/auth/login?redirect=%2Fchat']}>
          <Routes>
            <Route
              path="/auth/login"
              element={
                <PublicOnlyRoute>
                  <div data-testid="login-content">Login Form</div>
                </PublicOnlyRoute>
              }
            />
            <Route path="/chat" element={<div data-testid="chat">Chat Page</div>} />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      )

      expect(screen.getByTestId('chat')).toBeInTheDocument()
      expect(screen.queryByTestId('login-content')).not.toBeInTheDocument()
    })
  })

  describe('WorkspaceOnboardingPage Component', () => {
    it('13. Renders pathway cards and navigates to /workspaces/new and /invitations/accept', async () => {
      vi.mocked(workspaceService.getUserWorkspaces).mockResolvedValueOnce({ items: [] } as any)
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'alex@example.com', name: 'Alex' } as any,
      })

      render(
        <MemoryRouter initialEntries={['/onboarding']}>
          <Routes>
            <Route path="/onboarding" element={<WorkspaceOnboardingPage />} />
            <Route path="/workspaces/new" element={<div data-testid="new-ws-dest">New Workspace Page</div>} />
            <Route path="/invitations/accept" element={<div data-testid="accept-dest">Accept Page</div>} />
          </Routes>
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Workspace Onboarding')).toBeInTheDocument()
        expect(screen.getByText('Create a Workspace')).toBeInTheDocument()
        expect(screen.getByText('Join with Code or Invite')).toBeInTheDocument()
      })

      const createCard = screen.getByText('Create a Workspace')
      fireEvent.click(createCard)

      await waitFor(() => {
        expect(screen.getByTestId('new-ws-dest')).toBeInTheDocument()
      })
    })

    it('14. Renders inactive memberships and allows switching', async () => {
      const mockMemberships = [
        {
          workspace_id: 'ws-42',
          name: 'Research Lab',
          slug: 'research-lab',
          role: 'ADMIN',
          status: 'ACTIVE',
          public_id: 'w_test_42',
        },
      ]
      vi.mocked(workspaceService.getUserWorkspaces).mockResolvedValueOnce({
        items: mockMemberships,
      } as any)

      const mockSwitch = vi.fn().mockResolvedValueOnce(undefined)
      useWorkspaceStore.setState({
        switchWorkspace: mockSwitch,
      })

      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'alex@example.com', tenant_id: null } as any,
      })

      render(
        <MemoryRouter initialEntries={['/onboarding']}>
          <Routes>
            <Route path="/onboarding" element={<WorkspaceOnboardingPage />} />
            <Route path="/dashboard" element={<div data-testid="dashboard">Dashboard</div>} />
          </Routes>
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Existing Workspace Memberships')).toBeInTheDocument()
        expect(screen.getByText('Research Lab')).toBeInTheDocument()
      })

      const switchBtn = screen.getByRole('button', { name: /activate session/i })
      fireEvent.click(switchBtn)

      await waitFor(() => {
        expect(mockSwitch).toHaveBeenCalledWith('ws-42')
      })
    })

    it('15. Transient join code and invitation token banner appears when params present', async () => {
      vi.mocked(workspaceService.getUserWorkspaces).mockResolvedValueOnce({ items: [] } as any)
      useAuthStore.setState({
        status: 'AUTHENTICATED',
        user: { id: 'u1', email: 'alex@example.com' } as any,
      })

      render(
        <MemoryRouter initialEntries={['/onboarding?join_code=VR-123456&invitation_token=inv_tok_99']}>
          <WorkspaceOnboardingPage />
        </MemoryRouter>
      )

      await waitFor(() => {
        expect(screen.getByText(/Pending Join Context Detected/i)).toBeInTheDocument()
      })
    })
  })
})
