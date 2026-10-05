import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { QuotaBillingPage } from '@/pages/admin/QuotaBillingPage'
import { adminService, WorkspaceUserQuota } from '@/services/adminService'
import { workspaceSettingsService } from '@/services/workspaceSettingsService'
import { useAuthStore } from '@/stores/authStore'

describe('WS-B9: Quota Administration UI & User Quotas', () => {
  const mockWorkspaceId = 'ws-test-b9-001'

  const mockWorkspaceQuota = {
    tenant_id: mockWorkspaceId,
    monthly_token_limit: 10_000_000,
    monthly_budget_usd: 150.0,
    warning_threshold_pct: 0.8,
    is_hard_enforced: true,
    remaining_tokens: 8_500_000,
    remaining_budget_usd: 127.5,
  }

  const mockWorkspaceUsage = {
    workspace_id: mockWorkspaceId,
    billing_period_start: '2026-10-01',
    used_tokens: 1_500_000,
    used_queries: 120,
    monthly_token_limit: 10_000_000,
    monthly_budget_usd: 150.0,
    warning_threshold_pct: 0.8,
    is_hard_enforced: true,
    remaining_tokens: 8_500_000,
    remaining_budget_usd: 127.5,
    is_warning: false,
    is_exceeded: false,
  }

  const mockUserQuotas: WorkspaceUserQuota[] = [
    {
      id: 'uq-1',
      workspace_id: mockWorkspaceId,
      user_id: 'user-admin-1',
      monthly_token_budget: null, // Workspace pool
      is_hard_enforced: true,
      warning_threshold_pct: 0.8,
      user_email: 'admin@veritas.rag',
      user_display_name: 'Admin User',
      member_role: 'ADMIN',
      used_tokens: 800_000,
      used_queries: 60,
      workspace_token_limit: 10_000_000,
    },
    {
      id: 'uq-2',
      workspace_id: mockWorkspaceId,
      user_id: 'user-member-2',
      monthly_token_budget: 500_000,
      is_hard_enforced: true,
      warning_threshold_pct: 0.8,
      user_email: 'analyst@veritas.rag',
      user_display_name: 'Analyst Member',
      member_role: 'MEMBER',
      used_tokens: 250_000,
      used_queries: 25,
      workspace_token_limit: 10_000_000,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(adminService, 'getWorkspaceUsage').mockResolvedValue(mockWorkspaceUsage)
    vi.spyOn(adminService, 'getQuota').mockResolvedValue(mockWorkspaceQuota)
    vi.spyOn(adminService, 'getUserQuotas').mockResolvedValue(mockUserQuotas)
    vi.spyOn(workspaceSettingsService, 'getSettings').mockResolvedValue({
      data: {
        workspace_id: mockWorkspaceId,
        settings: { limits: { monthly_token_budget: 10_000_000 } },
        version: 1,
        updated_at: '2026-10-01T00:00:00Z',
      },
    } as any)
  })

  it('renders Team Member Quotas table for workspace Admin/Owner', async () => {
    useAuthStore.setState({
      user: {
        id: 'user-admin-1',
        email: 'admin@veritas.rag',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })

    render(
      <BrowserRouter>
        <QuotaBillingPage />
      </BrowserRouter>
    )

    const numFmt = (n: number) => n.toLocaleString()

    expect(await screen.findByText('Team Member Quotas & Attribution')).toBeInTheDocument()
    expect(screen.getByText('Admin User')).toBeInTheDocument()
    expect(screen.getByText('Analyst Member')).toBeInTheDocument()
    expect(screen.getByText(/Workspace Pool \(Uncapped\)/i)).toBeInTheDocument()
    expect(screen.getByText(`${numFmt(500000)} tokens`)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Set Quota/i })).toHaveLength(2)
  })

  it('allows Admin to open modal and update user token quota', async () => {
    const updateUserQuotaSpy = vi
      .spyOn(adminService, 'updateUserQuota')
      .mockResolvedValue({
        ...mockUserQuotas[1],
        monthly_token_budget: 750_000,
      })

    useAuthStore.setState({
      user: {
        id: 'user-admin-1',
        email: 'admin@veritas.rag',
        role: 'ADMIN',
        workspace_id: mockWorkspaceId,
      } as any,
    })

    render(
      <BrowserRouter>
        <QuotaBillingPage />
      </BrowserRouter>
    )

    const setQuotaBtns = await screen.findAllByRole('button', { name: /Set Quota/i })
    await userEvent.click(setQuotaBtns[1]) // Click on Analyst Member

    expect(await screen.findByText('Configure User Token Quota')).toBeInTheDocument()
    expect(screen.getAllByText('analyst@veritas.rag').length).toBeGreaterThanOrEqual(1)

    const input = screen.getByLabelText(/Monthly Token Ceiling/i)
    await userEvent.clear(input)
    await userEvent.type(input, '750000')

    const saveBtn = screen.getByRole('button', { name: /Save User Quota/i })
    await userEvent.click(saveBtn)

    await waitFor(() => {
      expect(updateUserQuotaSpy).toHaveBeenCalledWith(
        mockWorkspaceId,
        'user-member-2',
        expect.objectContaining({
          monthly_token_budget: 750000,
        })
      )
    })
  })

  it('renders read-only personal quota card for regular MEMBER', async () => {
    const numFmt = (n: number) => n.toLocaleString()
    const myQuota: WorkspaceUserQuota = {
      id: 'uq-me',
      workspace_id: mockWorkspaceId,
      user_id: 'user-member-2',
      monthly_token_budget: 500_000,
      is_hard_enforced: true,
      warning_threshold_pct: 0.8,
      user_email: 'analyst@veritas.rag',
      user_display_name: 'Analyst Member',
      member_role: 'MEMBER',
      used_tokens: 150_000,
      used_queries: 18,
      workspace_token_limit: 10_000_000,
    }
    vi.spyOn(adminService, 'getMyUserQuota').mockResolvedValue(myQuota)

    useAuthStore.setState({
      user: {
        id: 'user-member-2',
        email: 'analyst@veritas.rag',
        role: 'MEMBER',
        workspace_id: mockWorkspaceId,
      } as any,
    })

    render(
      <BrowserRouter>
        <QuotaBillingPage />
      </BrowserRouter>
    )

    expect(await screen.findByText('My Personal Quota & Usage')).toBeInTheDocument()
    expect(screen.getByText(numFmt(150000))).toBeInTheDocument()
    expect(screen.getByText(new RegExp(`Ceiling: ${numFmt(500000)} tokens`, 'i'))).toBeInTheDocument()
    expect(screen.queryByText('Team Member Quotas & Attribution')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Adjust Quotas/i })).not.toBeInTheDocument()
  })
})
