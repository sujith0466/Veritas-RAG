import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkspaceSelector } from '@/components/navigation/WorkspaceSelector'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useAuthStore } from '@/stores/authStore'
import { workspaceService } from '@/services/workspaceService'

const mockToast = vi.fn()

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: mockToast,
    dismiss: vi.fn(),
  }),
}))

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    getUserWorkspaces: vi.fn(),
    switchWorkspace: vi.fn(),
  },
}))

describe('Package 1.3: WorkspaceSelector Component & Switching Workflow', () => {
  const mockWorkspacesList = {
    success: true,
    total: 2,
    items: [
      {
        workspace_id: 'ws-111',
        public_id: 'WS-ALPHA1',
        name: 'Alpha Corporation',
        slug: 'alpha-corp',
        role: 'OWNER',
        status: 'ACTIVE',
        is_active_context: true,
      },
      {
        workspace_id: 'ws-222',
        public_id: 'WS-BETA02',
        name: 'Beta Labs',
        slug: 'beta-labs',
        role: 'MEMBER',
        status: 'ACTIVE',
        is_active_context: false,
      },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.setState({
      user: {
        id: 'usr-1',
        email: 'user@example.com',
        role: 'owner' as any,
        tenant_id: 'ws-111',
        workspace_id: 'ws-111',
      },
    } as any)

    useWorkspaceStore.setState({
      currentWorkspace: {
        id: 'ws-111',
        public_id: 'WS-ALPHA1',
        name: 'Alpha Corporation',
        slug: 'alpha-corp',
        status: 'ACTIVE',
        provisioning_status: 'READY',
        updated_at: new Date().toISOString(),
      },
      workspaces: [],
      switchWorkspace: vi.fn(),
    } as any)

    vi.mocked(workspaceService.getUserWorkspaces).mockResolvedValue(mockWorkspacesList)
  })

  it('renders active workspace name and authoritative role in trigger button', async () => {
    render(
      <MemoryRouter>
        <WorkspaceSelector />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByTestId('workspace-selector-trigger')).toBeInTheDocument()
      expect(screen.getByText('Alpha Corporation')).toBeInTheDocument()
      expect(screen.getByText('OWNER')).toBeInTheDocument()
    })
  })

  it('opens dropdown and displays list of user workspaces with roles', async () => {
    render(
      <MemoryRouter>
        <WorkspaceSelector />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(workspaceService.getUserWorkspaces).toHaveBeenCalledTimes(1)
    })

    // Click trigger to open dropdown
    fireEvent.click(screen.getByTestId('workspace-selector-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('workspace-selector-dropdown')).toBeInTheDocument()
      expect(screen.getByTestId('workspace-item-ws-111')).toBeInTheDocument()
      expect(screen.getByTestId('workspace-item-ws-222')).toBeInTheDocument()
      expect(screen.getByText('Beta Labs')).toBeInTheDocument()
      expect(screen.getByText('MEMBER')).toBeInTheDocument()
    })

    // Actions are rendered
    expect(screen.getByTestId('create-workspace-nav-btn')).toBeInTheDocument()
    expect(screen.getByTestId('create-workspace-nav-btn')).toHaveAttribute('href', '/workspaces/new')
    expect(screen.getByTestId('join-workspace-nav-btn')).toBeInTheDocument()
    expect(screen.getByTestId('join-workspace-nav-btn')).toHaveAttribute('href', '/workspaces/join')
  })

  it('switches workspace when a different workspace item is clicked', async () => {
    const mockSwitch = vi.fn().mockResolvedValue({
      workspace_id: 'ws-222',
      workspace_name: 'Beta Labs',
      role: 'MEMBER',
      access_token: 'new-jwt-token',
    })
    useWorkspaceStore.setState({ switchWorkspace: mockSwitch } as any)

    render(
      <MemoryRouter>
        <WorkspaceSelector />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(workspaceService.getUserWorkspaces).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByTestId('workspace-selector-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('workspace-item-ws-222')).toBeInTheDocument()
    })

    // Click target workspace Beta Labs
    fireEvent.click(screen.getByTestId('workspace-item-ws-222'))

    await waitFor(() => {
      expect(mockSwitch).toHaveBeenCalledTimes(1)
      expect(mockSwitch).toHaveBeenCalledWith('ws-222')
    })

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'success',
          title: 'Workspace Switched',
        })
      )
    })
  })

  it('handles workspace switch failure gracefully with error toast', async () => {
    const mockSwitch = vi.fn().mockRejectedValue({
      response: {
        data: {
          detail: 'You are not an active member of this workspace',
        },
      },
    })
    useWorkspaceStore.setState({ switchWorkspace: mockSwitch } as any)

    render(
      <MemoryRouter>
        <WorkspaceSelector />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(workspaceService.getUserWorkspaces).toHaveBeenCalledTimes(1)
    })

    fireEvent.click(screen.getByTestId('workspace-selector-trigger'))

    await waitFor(() => {
      expect(screen.getByTestId('workspace-item-ws-222')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('workspace-item-ws-222'))

    await waitFor(() => {
      expect(mockSwitch).toHaveBeenCalledWith('ws-222')
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'error',
          title: 'Switch Failed',
          message: 'You are not an active member of this workspace',
        })
      )
    })
  })
})
