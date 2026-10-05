import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { DemoRoleSwitcher } from '@/components/navigation/DemoRoleSwitcher'
import { useAuthStore } from '@/stores/authStore'
import { authService } from '@/services/auth/authService'
import type { UserContext } from '@/types'

vi.mock('@/services/auth/authService', () => ({
  authService: {
    switchDemoRole: vi.fn(),
    resetDemoRole: vi.fn(),
    fetchBackendProfile: vi.fn(),
  },
}))

vi.mock('@/stores/workspaceStore', () => ({
  useWorkspaceStore: {
    getState: vi.fn(() => ({
      fetchCurrentWorkspace: vi.fn().mockResolvedValue({}),
      resetWorkspaceResolution: vi.fn(),
    })),
  },
}))

describe('DemoRoleSwitcher Frontend Integration', () => {
  const baseUser: UserContext = {
    id: 'test-user-uuid-1',
    email: 'test-user@example.com',
    role: 'owner',
    tenant_id: 'ws-uuid-1',
    workspace_name: 'Test Workspace',
    full_name: 'Test Operator',
    is_active: true,
    demo_role_switcher_enabled: false,
    demo_simulated: false,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      status: 'AUTHENTICATED',
      user: null,
      token: 'mock-token',
    })
  })

  it('does NOT render when demo_role_switcher_enabled is false or absent', () => {
    useAuthStore.setState({
      user: { ...baseUser, demo_role_switcher_enabled: false },
    })

    const { container } = render(<DemoRoleSwitcher />)
    expect(container.firstChild).toBeNull()
  })

  it('renders Demo Role Switcher trigger when demo_role_switcher_enabled is true', () => {
    useAuthStore.setState({
      user: { ...baseUser, demo_role_switcher_enabled: true, role: 'owner' },
    })

    render(<DemoRoleSwitcher />)
    const button = screen.getByRole('button', { name: /demo role switcher/i })
    expect(button).toBeInTheDocument()
    expect(screen.getByText(/owner/i)).toBeInTheDocument()
  })

  it('displays simulated badge when demo_simulated is true', () => {
    useAuthStore.setState({
      user: {
        ...baseUser,
        demo_role_switcher_enabled: true,
        demo_simulated: true,
        role: 'member',
      },
    })

    render(<DemoRoleSwitcher />)
    const button = screen.getByRole('button', { name: /demo role switcher/i })
    expect(button).toBeInTheDocument()
    expect(screen.getByText(/member/i)).toBeInTheDocument()
  })

  it('invokes switchDemoRole and updates authStore upon selecting a role', async () => {
    const user = userEvent.setup()
    useAuthStore.setState({
      user: { ...baseUser, demo_role_switcher_enabled: true, role: 'owner' },
    })

    const updatedUser: UserContext = {
      ...baseUser,
      demo_role_switcher_enabled: true,
      demo_simulated: true,
      role: 'viewer',
    }

    vi.mocked(authService.switchDemoRole).mockResolvedValueOnce({
      access_token: 'new-simulated-token',
      role: 'viewer',
      workspace_id: 'ws-uuid-1',
      demo_simulated: true,
    })

    vi.mocked(authService.fetchBackendProfile).mockResolvedValueOnce(updatedUser)

    render(<DemoRoleSwitcher />)
    const button = screen.getByRole('button', { name: /demo role switcher/i })
    await user.click(button)

    // Find "Viewer" option in dropdown
    const viewerOption = await screen.findByText(/^viewer$/i)
    await user.click(viewerOption)

    await waitFor(() => {
      expect(authService.switchDemoRole).toHaveBeenCalledWith('viewer', 'ws-uuid-1')
      expect(authService.fetchBackendProfile).toHaveBeenCalled()
    })
  })

  it('invokes resetDemoRole when Reset to Base Role is clicked', async () => {
    const user = userEvent.setup()
    useAuthStore.setState({
      user: {
        ...baseUser,
        demo_role_switcher_enabled: true,
        demo_simulated: true,
        role: 'viewer',
      },
    })

    const resetUser: UserContext = {
      ...baseUser,
      demo_role_switcher_enabled: true,
      demo_simulated: false,
      role: 'owner',
    }

    vi.mocked(authService.resetDemoRole).mockResolvedValueOnce({
      access_token: 'reset-token',
      role: 'owner',
      workspace_id: 'ws-uuid-1',
      demo_simulated: false,
    })

    vi.mocked(authService.fetchBackendProfile).mockResolvedValueOnce(resetUser)

    render(<DemoRoleSwitcher />)
    const button = screen.getByRole('button', { name: /demo role switcher/i })
    await user.click(button)

    const resetButton = await screen.findByText(/reset to base role/i)
    await user.click(resetButton)

    await waitFor(() => {
      expect(authService.resetDemoRole).toHaveBeenCalled()
      expect(authService.fetchBackendProfile).toHaveBeenCalled()
    })
  })
})
