import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkspaceSettings } from '@/pages/settings/WorkspaceSettings'
import { workspaceService } from '@/services/workspaceService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'
import { useWorkspaceStore } from '@/stores/workspaceStore'

describe('Workstream E: Active Join Code Expiration Management', () => {
  const mockWorkspace = {
    id: 'ws-uuid-111',
    public_id: 'wrk_pub111abc',
    name: 'Acme Global Corp',
    slug: 'acme-global',
    role: 'ADMIN',
    status: 'ACTIVE',
    updated_at: '2026-10-01T00:00:00Z',
  }

  beforeEach(() => {
    vi.clearAllMocks()

    useAuthStore.setState({
      user: {
        id: 'usr-admin-1',
        email: 'admin@acme.org',
        role: 'ADMIN' as any,
        workspace_id: 'ws-uuid-111',
        tenant_id: 'ws-uuid-111',
        workspace_name: 'Acme Global Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-admin-token',
    })

    useWorkspaceStore.setState({
      currentWorkspace: mockWorkspace as any,
      workspaces: [mockWorkspace as any],
    })
  })

  it('WS-E: Admin can update active Join Code expiration without code regeneration', async () => {
    const initialSettings = {
      enabled: true,
      has_code: true,
      default_role: 'MEMBER' as const,
      require_approval: false,
      max_uses: null,
      current_uses: 5,
      expires_at: '2026-11-01T00:00:00Z',
    }

    vi.spyOn(userService, 'getProfile').mockResolvedValue({
      data: { profile_data: { workspace_name: 'Acme Global Corp' } },
    } as any)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue({
      success: true,
      data: {
        workspace_id: 'ws-uuid-111',
        settings: { general: { retention_days: 90, default_language: 'en' } },
        schema_version: 1,
        version: 1,
        settings_hash: 'hash-abc',
        updated_at: '2026-10-01T00:00:00Z',
      },
    } as any)
    vi.spyOn(workspaceService, 'getCurrentWorkspace').mockResolvedValue({
      success: true,
      data: { workspace_id: 'ws-uuid-111', name: 'Acme Global Corp', status: 'ACTIVE' },
    } as any)
    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValue(initialSettings as any)

    const patchSpy = vi.spyOn(workspaceService, 'patchJoinCodeSettings').mockResolvedValue({
      ...initialSettings,
      expires_at: '2027-01-01T00:00:00Z', // 90 days later
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Active Join Code')).toBeInTheDocument()
      expect(screen.getByLabelText('Active Code Expiration')).toBeInTheDocument()
    })

    // Change expiration to 90 Days
    const expSelect = screen.getByLabelText('Active Code Expiration')
    fireEvent.change(expSelect, { target: { value: '90' } })

    // Submit form
    const saveBtn = screen.getByRole('button', { name: /Save Join Code Settings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith('ws-uuid-111', {
        enabled: true,
        default_role: 'MEMBER',
        require_approval: false,
        max_uses: null,
        expires_in_days: 90,
      })
    })
  })

  it('WS-E: Admin can set active Join Code expiration to Never (expires_in_days=0)', async () => {
    useAuthStore.setState({
      user: {
        id: 'usr-admin-1',
        email: 'admin@acme.org',
        role: 'OWNER' as any,
        workspace_id: 'ws-uuid-111',
        tenant_id: 'ws-uuid-111',
        workspace_name: 'Acme Global Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'jwt-admin-token',
    })

    const initialSettings = {
      enabled: true,
      has_code: true,
      default_role: 'MEMBER' as const,
      require_approval: false,
      max_uses: null,
      current_uses: 2,
      expires_at: '2026-11-01T00:00:00Z',
    }

    vi.spyOn(userService, 'getProfile').mockResolvedValue({
      data: { profile_data: { workspace_name: 'Acme Global Corp' } },
    } as any)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue({
      success: true,
      data: {
        workspace_id: 'ws-uuid-111',
        settings: { general: { retention_days: 90, default_language: 'en' } },
        schema_version: 1,
        version: 1,
        settings_hash: 'hash-abc',
        updated_at: '2026-10-01T00:00:00Z',
      },
    } as any)
    vi.spyOn(workspaceService, 'getCurrentWorkspace').mockResolvedValue({
      success: true,
      data: { workspace_id: 'ws-uuid-111', name: 'Acme Global Corp', status: 'ACTIVE' },
    } as any)
    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValue(initialSettings as any)

    const patchSpy = vi.spyOn(workspaceService, 'patchJoinCodeSettings').mockResolvedValue({
      ...initialSettings,
      expires_at: null, // Never
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Active Join Code')).toBeInTheDocument()
      expect(screen.getByLabelText('Active Code Expiration')).toBeInTheDocument()
    })

    // Change expiration to Never ('0')
    const expSelect = screen.getByLabelText('Active Code Expiration')
    fireEvent.change(expSelect, { target: { value: '0' } })

    // Submit form
    const saveBtn = screen.getByRole('button', { name: /Save Join Code Settings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith('ws-uuid-111', {
        enabled: true,
        default_role: 'MEMBER',
        require_approval: false,
        max_uses: null,
        expires_in_days: 0,
      })
    })
  })

  it('UI Remediation: 60 Days option in regenerate modal, mb-6 spacing on credentials card, and version badge absent', async () => {
    const initialSettings = {
      enabled: true,
      has_code: true,
      default_role: 'MEMBER' as const,
      require_approval: false,
      max_uses: null,
      current_uses: 2,
      expires_at: '2026-11-01T00:00:00Z',
    }

    vi.spyOn(userService, 'getProfile').mockResolvedValue({
      data: { profile_data: { workspace_name: 'Acme Global Corp' } },
    } as any)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue({
      success: true,
      data: {
        workspace_id: 'ws-uuid-111',
        settings: { general: { retention_days: 90, default_language: 'en' } },
        schema_version: 1,
        version: 9,
        settings_hash: 'hash-abc',
        updated_at: '2026-10-01T00:00:00Z',
      },
    } as any)
    vi.spyOn(workspaceService, 'getCurrentWorkspace').mockResolvedValue({
      success: true,
      data: { workspace_id: 'ws-uuid-111', name: 'Acme Global Corp', status: 'ACTIVE' },
    } as any)
    vi.spyOn(workspaceService, 'getJoinCodeSettings').mockResolvedValue(initialSettings as any)
    vi.spyOn(workspaceService, 'getJoinAccess').mockResolvedValue({
      has_code: true,
      join_code: 'VR-ACTIVE1',
      join_link: 'http://localhost:5173/join?workspace_id=wrk_pub111abc&code=VR-ACTIVE1',
      expires_at: '2026-11-01T00:00:00Z',
    } as any)

    const regenSpy = vi.spyOn(workspaceService, 'regenerateJoinCode').mockResolvedValue({
      join_code: 'VR-NEW60D1',
      join_link: 'http://localhost:5173/join?workspace_id=wrk_pub111abc&code=VR-NEW60D1',
      expires_at: '2026-12-31T00:00:00Z',
      max_uses: null,
    } as any)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    // FIX-03: Verify Version 9 badge is absent
    await waitFor(() => {
      expect(screen.queryByText(/Version 9/i)).not.toBeInTheDocument()
    })

    // FIX-02: Verify active credentials card is rendered and has mb-6 spacing
    const credsCard = await screen.findByTestId('active-join-credentials-card')
    expect(credsCard).toHaveClass('mb-6')
    expect(screen.getByText('VR-ACTIVE1')).toBeInTheDocument()

    // FIX-01: Open Regenerate Modal and select 60 Days
    const regenTriggerBtn = screen.getByRole('button', { name: /Regenerate Code/i })
    fireEvent.click(regenTriggerBtn)

    const validitySelect = await screen.findByLabelText(/New Code Validity \(Days\)/i)
    
    // Verify 60 Days option exists in dropdown
    const options = Array.from((validitySelect as HTMLSelectElement).options).map(o => o.text)
    expect(options).toContain('60 Days')

    fireEvent.change(validitySelect, { target: { value: '60' } })

    const confirmRegenBtn = screen.getByRole('button', { name: /Confirm & Regenerate/i })
    fireEvent.click(confirmRegenBtn)

    await waitFor(() => {
      expect(regenSpy).toHaveBeenCalledWith('ws-uuid-111', {
        expires_in_days: 60,
        max_uses: null,
      })
    })
  })
})
