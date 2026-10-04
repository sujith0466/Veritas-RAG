import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { WorkspaceSettings } from '@/pages/settings/WorkspaceSettings'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { userService } from '@/services/userService'
import { useAuthStore } from '@/stores/authStore'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('Canonical Workspace Settings & Optimistic Concurrency (ADMIN-02)', () => {
  const sampleSettingsResponse = {
    success: true,
    data: {
      workspace_id: 'ws-123',
      settings: {
        general: {
          retention_days: 180,
          default_language: 'en',
        },
      },
      schema_version: 1,
      version: 5,
      settings_hash: 'abcdef1234567890',
      updated_at: '2026-10-04T01:00:00Z',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.setState({
      user: {
        id: 'u-1',
        email: 'admin@example.com',
        role: 'ADMIN' as any,
        workspace_id: 'ws-123',
        tenant_id: 'ws-123',
        workspace_name: 'Veritas Corp',
      } as any,
      status: 'AUTHENTICATED',
      token: 'mock-jwt-token',
      error: undefined,
    })

    vi.spyOn(userService, 'getProfile').mockResolvedValue({
      data: {
        profile_data: { workspace_name: 'Veritas Corp' },
      },
    } as any)

    vi.spyOn(userService, 'updateProfile').mockResolvedValue({} as any)
  })

  it('loads canonical settings and displays version and retention policy', async () => {
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(sampleSettingsResponse)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(workspaceSettingsService.getSettings).toHaveBeenCalledWith('ws-123')
    })

    expect(await screen.findByDisplayValue('Veritas Corp')).toBeInTheDocument()
    expect(screen.getByText(/Version 5/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('180 Days')).toBeInTheDocument()
    expect(screen.queryByLabelText(/Primary Data Region/i)).not.toBeInTheDocument()
  })

  it('navigates to /admin/members when Manage Team button is clicked', async () => {
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(sampleSettingsResponse)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    const manageBtn = await screen.findByRole('button', { name: /Manage Team/i })
    fireEvent.click(manageBtn)

    expect(mockNavigate).toHaveBeenCalledWith('/admin/members')
  })

  it('saves settings with expected_updated_at concurrency lock', async () => {
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(sampleSettingsResponse)
    const patchSpy = vi.spyOn(workspaceSettingsService, 'patchSettings').mockResolvedValue({
      success: true,
      data: {
        ...sampleSettingsResponse.data,
        version: 6,
        updated_at: '2026-10-04T01:05:00Z',
      },
    })

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByDisplayValue('180 Days')).toBeInTheDocument()
    })

    // Change retention to 365 Days
    const select = screen.getByLabelText(/Log Retention Policy/i)
    fireEvent.change(select, { target: { value: '365' } })

    const saveBtn = screen.getByRole('button', { name: /Save Workspace Settings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      expect(patchSpy).toHaveBeenCalledWith(
        'ws-123',
        '2026-10-04T01:00:00Z',
        {
          general: {
            retention_days: 365,
          },
        }
      )
    })
  })

  it('handles 409 concurrency conflict by alerting and re-fetching latest settings', async () => {
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue(sampleSettingsResponse)
    const conflictError: any = new Error('Settings conflict')
    conflictError.response = { status: 409, data: { detail: 'Conflict' } }
    vi.spyOn(workspaceSettingsService, 'patchSettings').mockRejectedValue(conflictError)

    render(
      <MemoryRouter>
        <WorkspaceSettings />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByDisplayValue('180 Days')).toBeInTheDocument()
    })

    const saveBtn = screen.getByRole('button', { name: /Save Workspace Settings/i })
    fireEvent.click(saveBtn)

    await waitFor(() => {
      // Upon 409, getSettings should be called again to reload fresh data
      expect(workspaceSettingsService.getSettings).toHaveBeenCalledTimes(2)
    })
  })
})
