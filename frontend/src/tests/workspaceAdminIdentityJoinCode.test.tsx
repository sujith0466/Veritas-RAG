import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkspaceSettings } from '@/pages/settings/WorkspaceSettings'
import { workspaceService } from '@/services/workspaceService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('Workspace Admin Identity & Join Code Management UI (WS-A9)', () => {
  const mockWorkspace = {
    id: 'ws-uuid-999',
    public_id: 'wrk_pub999xyz',
    name: 'Acme Research Corp',
    slug: 'acme-research',
    role: 'OWNER',
    member_count: 5,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    membership_status: 'ACTIVE',
  }

  const mockCurrentWsResponse = {
    success: true,
    data: {
      workspace_id: 'ws-uuid-999',
      public_id: 'wrk_pub999xyz',
      name: 'Acme Research Corp',
      slug: 'acme-research',
      status: 'ACTIVE',
    },
  }

  const mockJoinCodeSettingsActive = {
    enabled: true,
    has_code: true,
    default_role: 'MEMBER' as const,
    require_approval: false,
    max_uses: 50,
    current_uses: 12,
    expires_at: '2026-11-01T00:00:00Z',
  }

  const mockSettingsResponse = {
    success: true,
    data: {
      workspace_id: 'ws-uuid-999',
      settings: {
        general: {
          retention_days: 90,
          default_language: 'en',
        },
      },
      schema_version: 1,
      version: 1,
      settings_hash: 'hash12345',
      updated_at: '2026-10-01T00:00:00Z',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()

    // Auth Store state
    useAuthStore.setState({
      user: {
        id: 'usr-1',
        email: 'owner@acme.org',
        role: 'OWNER' as any,
        workspace_id: 'ws-uuid-999',
        tenant_id: 'ws-uuid-999',
        workspace_name: 'Acme Research Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-token',
    })

    // Workspace Store state
    useWorkspaceStore.setState({
      currentWorkspace: mockWorkspace as any,
      workspaces: [mockWorkspace as any],
    })

    vi.spyOn(userService, 'getProfile').mockResolvedValue({
      data: { profile_data: { workspace_name: 'Acme Research Corp' } },
    } as any)

    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(mockSettingsResponse)
    vi.spyOn(workspaceService, 'getCurrentWorkspace').mockResolvedValue(mockCurrentWsResponse as any)
    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValue(mockJoinCodeSettingsActive as any)
  })

  it('renders Workspace Identity card with Public Workspace ID and diagnostic UUID (A9.1-A9.3)', async () => {
    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    // Verify Workspace Identity Heading
    expect(await screen.findByText('Workspace Identity')).toBeInTheDocument()

    // Verify Public Workspace ID in badge and read-only input
    expect(await screen.findByDisplayValue('wrk_pub999xyz')).toBeInTheDocument()
    expect(screen.getByText(/ID:\s*wrk_pub999xyz/i)).toBeInTheDocument()

    // Verify Slug
    expect(screen.getByDisplayValue('acme-research')).toBeInTheDocument()

    // Verify Diagnostic UUID
    expect(screen.getByDisplayValue('ws-uuid-999')).toBeInTheDocument()

    // Verify Copy Public ID Button exists
    const copyPublicIdBtn = screen.getByRole('button', { name: /Copy Public ID/i })
    expect(copyPublicIdBtn).toBeInTheDocument()
  })

  it('renders Active Join Code status, preview and metrics for OWNER/ADMIN (A9.5-A9.7)', async () => {
    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(workspaceService.getJoinCodeSettings).toHaveBeenCalledWith('ws-uuid-999')
    })

    // Verify status badge
    expect(await screen.findByText('Active Join Code')).toBeInTheDocument()

    // Verify usage metrics (12 / 50 limit)
    expect(screen.getByText(/\/ 50 limit/i)).toBeInTheDocument()

    // Verify Regenerate button is visible for existing code
    expect(screen.getByRole('button', { name: /Regenerate Code/i })).toBeInTheDocument()
  })

  it('allows generating a new Join Code and shows one-time plaintext modal (A9.8-A9.10)', async () => {
    // Mock configured without active code initially
    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValueOnce({
      enabled: true,
      has_code: false,
      default_role: 'MEMBER',
      require_approval: false,
      max_uses: null,
      current_uses: 0,
      expires_at: null,
    } as any)

    const generateSpy = vi.spyOn(workspaceService, 'generateJoinCode').mockResolvedValue({
      success: true,
      join_code: 'VR-789ABC',
      expires_at: '2026-11-03T00:00:00Z',
      default_role: 'MEMBER',
      warning: 'Store this code safely',
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    // Should show "Not Configured"
    expect(await screen.findByText('Not Configured')).toBeInTheDocument()

    // Click Generate Join Code
    const generateBtn = screen.getByRole('button', { name: /Generate Join Code/i })
    fireEvent.click(generateBtn)

    await waitFor(() => {
      expect(generateSpy).toHaveBeenCalledWith('ws-uuid-999', expect.objectContaining({
        default_role: 'MEMBER',
        require_approval: false,
      }))
    })

    // One-Time Plaintext Reveal Modal must appear
    expect(await screen.findByText('Join Code Generated')).toBeInTheDocument()
    expect(screen.getAllByText('VR-789ABC').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Strict One-Time Reveal')).toBeInTheDocument()

    // Click Dismiss ("I Have Copied This Code (Dismiss)")
    const dismissBtn = screen.getByRole('button', { name: /I Have Copied This Code/i })
    fireEvent.click(dismissBtn)

    // Modal should close, but Active Join Credentials card remains visible in current admin view (Plan B)
    await waitFor(() => {
      expect(screen.queryByText('Join Code Generated')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('active-join-credentials-card')).toBeInTheDocument()
    expect(screen.getByText('VR-789ABC')).toBeInTheDocument()
    expect(screen.getByText(/workspaces\/join\?workspace_id=wrk_pub999xyz&join_code=VR-789ABC/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy join code' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy join link' })).toBeInTheDocument()
  })

  it('triggers confirmation dialog before regenerating an existing code and replaces active credentials (A9.11, Plan B)', async () => {
    const regenerateSpy = vi.spyOn(workspaceService, 'regenerateJoinCode').mockResolvedValue({
      success: true,
      join_code: 'VR-REGEN9',
      expires_at: '2026-11-04T00:00:00Z',
      default_role: 'MEMBER',
      warning: 'New code generated',
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    const regenBtn = await screen.findByRole('button', { name: /Regenerate Code/i })
    fireEvent.click(regenBtn)

    // Confirmation dialog should be displayed
    expect(await screen.findByText('Regenerate Join Code?')).toBeInTheDocument()
    expect(screen.getByText(/Regenerating will immediately invalidate any previous Join Code/i)).toBeInTheDocument()

    // Click Confirm
    const confirmBtn = screen.getByRole('button', { name: /Confirm & Regenerate/i })
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(regenerateSpy).toHaveBeenCalledWith('ws-uuid-999', expect.anything())
    })

    // Reveal modal with new code
    expect(await screen.findByText('Join Code Generated')).toBeInTheDocument()
    expect(screen.getAllByText('VR-REGEN9').length).toBeGreaterThanOrEqual(1)

    // Dismiss modal and verify new code is displayed in active credentials card
    const dismissBtn = screen.getByRole('button', { name: /I Have Copied This Code/i })
    fireEvent.click(dismissBtn)

    await waitFor(() => {
      expect(screen.queryByText('Join Code Generated')).not.toBeInTheDocument()
    })
    expect(screen.getByTestId('active-join-credentials-card')).toBeInTheDocument()
    expect(screen.getByText('VR-REGEN9')).toBeInTheDocument()
    expect(screen.getByText(/workspaces\/join\?workspace_id=wrk_pub999xyz&join_code=VR-REGEN9/)).toBeInTheDocument()
    expect(screen.queryByText('VR-789ABC')).not.toBeInTheDocument()
  })

  it('updates Join Code policy settings (enabled, role, max_uses) (A9.12)', async () => {
    const updateSpy = vi.spyOn(workspaceService, 'patchJoinCodeSettings').mockResolvedValue({
      ...mockJoinCodeSettingsActive,
      default_role: 'VIEWER',
      max_uses: 100,
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Active Join Code')).toBeInTheDocument()
    })

    // Change role to VIEWER
    const roleSelect = screen.getByLabelText(/Default Role/i)
    fireEvent.change(roleSelect, { target: { value: 'VIEWER' } })

    // Change max uses to 100
    const maxUsesInput = screen.getByLabelText(/Max Uses/i)
    fireEvent.change(maxUsesInput, { target: { value: '100' } })

    // Submit settings form
    const saveSettingsBtn = screen.getByRole('button', { name: /Save Join Code Settings/i })
    fireEvent.click(saveSettingsBtn)

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith('ws-uuid-999', {
        enabled: true,
        default_role: 'VIEWER',
        require_approval: false,
        max_uses: 100,
      })
    })
  })

  it('restricts Join Code management controls for VIEWER role (A9.13)', async () => {
    // Current user is VIEWER
    useAuthStore.setState({
      user: {
        id: 'usr-viewer',
        email: 'viewer@acme.org',
        role: 'VIEWER' as any,
        workspace_id: 'ws-uuid-999',
        tenant_id: 'ws-uuid-999',
        workspace_name: 'Acme Research Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-token',
    })

    useWorkspaceStore.setState({
      currentWorkspace: {
        ...mockWorkspace,
        role: 'VIEWER',
      } as any,
    })

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    // Should display permission warning
    expect(await screen.findByText(/Join Code generation and access policies require Workspace Owner or Admin permissions/i)).toBeInTheDocument()

    // Should NOT have Generate or Regenerate buttons
    expect(screen.queryByRole('button', { name: /Generate Join Code/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Regenerate Code/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Save Join Code Settings/i })).not.toBeInTheDocument()
  })
})
